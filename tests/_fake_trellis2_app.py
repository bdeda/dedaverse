# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""A stand-in for TRELLIS.2's ``app.py`` Gradio server, for testing the Trellis client.

It mirrors the real app's endpoint wiring (names, argument order, a ``gr.State`` that
lives server-side per session, and the ``.then()`` chains) but replaces the model with a
tiny canned result, so no GPU or TRELLIS.2 install is needed. Requires ``gradio==6.0.1``,
the version TRELLIS.2 pins.

Run: ``python tests/_fake_trellis2_app.py [port]``
"""
import json
import os
import struct
import sys
import tempfile

import gradio as gr
from PIL import Image

TMP_DIR = os.path.join(tempfile.gettempdir(), 'fake_trellis2')
_SESSIONS = {}


def make_glb() -> bytes:
    """Return the bytes of a minimal valid GLB containing one triangle."""
    positions = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    gltf = {
        'asset': {'version': '2.0'},
        'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3',
                       'min': [0, 0, 0], 'max': [1, 1, 0]}],
        'bufferViews': [{'buffer': 0, 'byteLength': len(positions)}],
        'buffers': [{'byteLength': len(positions)}],
    }
    js = json.dumps(gltf).encode()
    js += b' ' * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(positions)
    return (struct.pack('<III', 0x46546C67, 2, total)
            + struct.pack('<II', len(js), 0x4E4F534A) + js
            + struct.pack('<II', len(positions), 0x004E4942) + positions)


def start_session(req: gr.Request):
    os.makedirs(os.path.join(TMP_DIR, str(req.session_hash)), exist_ok=True)


def end_session(req: gr.Request):
    pass


def preprocess_image(image: Image.Image) -> Image.Image:
    return image.convert('RGBA')


def get_seed(randomize_seed: bool, seed: int) -> int:
    return 12345 if randomize_seed else seed


def image_to_3d(
    image: Image.Image, seed: int, resolution: str,
    ss_guidance_strength: float, ss_guidance_rescale: float, ss_sampling_steps: int, ss_rescale_t: float,
    shape_slat_guidance_strength: float, shape_slat_guidance_rescale: float,
    shape_slat_sampling_steps: int, shape_slat_rescale_t: float,
    tex_slat_guidance_strength: float, tex_slat_guidance_rescale: float,
    tex_slat_sampling_steps: int, tex_slat_rescale_t: float,
    req: gr.Request,
    progress=gr.Progress(track_tqdm=True),
):
    state = {'seed': seed, 'resolution': resolution, 'ss_steps': ss_sampling_steps}
    _SESSIONS[req.session_hash] = state
    return state, f'<div>preview seed={seed} resolution={resolution}</div>'


def extract_glb(state: dict, decimation_target: int, texture_size: int, req: gr.Request,
                progress=gr.Progress(track_tqdm=True)):
    # Like the real app, this only works if the session's State survived between calls.
    if not state or state != _SESSIONS.get(req.session_hash):
        raise gr.Error('no model in this session: generate one first')
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    os.makedirs(user_dir, exist_ok=True)  # the real app does this before exporting
    path = os.path.join(user_dir, f'sample_{decimation_target}_{texture_size}.glb')
    with open(path, 'wb') as f:
        f.write(make_glb())
    return path, path


with gr.Blocks(delete_cache=(600, 600)) as demo:
    with gr.Row():
        with gr.Column():
            image_prompt = gr.Image(label='Image Prompt', format='png', image_mode='RGBA', type='pil')
            resolution = gr.Radio(['512', '1024', '1536'], label='Resolution', value='1024')
            seed = gr.Slider(0, 2147483647, label='Seed', value=0, step=1)
            randomize_seed = gr.Checkbox(label='Randomize Seed', value=True)
            decimation_target = gr.Slider(100000, 1000000, label='Decimation Target', value=500000, step=10000)
            texture_size = gr.Slider(1024, 4096, label='Texture Size', value=2048, step=1024)
            generate_btn = gr.Button('Generate')
            with gr.Accordion(label='Advanced Settings', open=False):
                ss_guidance_strength = gr.Slider(1.0, 10.0, value=7.5)
                ss_guidance_rescale = gr.Slider(0.0, 1.0, value=0.7)
                ss_sampling_steps = gr.Slider(1, 50, value=12, step=1)
                ss_rescale_t = gr.Slider(1.0, 6.0, value=5.0)
                shape_slat_guidance_strength = gr.Slider(1.0, 10.0, value=7.5)
                shape_slat_guidance_rescale = gr.Slider(0.0, 1.0, value=0.5)
                shape_slat_sampling_steps = gr.Slider(1, 50, value=12, step=1)
                shape_slat_rescale_t = gr.Slider(1.0, 6.0, value=3.0)
                tex_slat_guidance_strength = gr.Slider(1.0, 10.0, value=1.0)
                tex_slat_guidance_rescale = gr.Slider(0.0, 1.0, value=0.0)
                tex_slat_sampling_steps = gr.Slider(1, 50, value=12, step=1)
                tex_slat_rescale_t = gr.Slider(1.0, 6.0, value=3.0)
        with gr.Column(scale=10):
            with gr.Walkthrough(selected=0) as walkthrough:
                with gr.Step('Preview', id=0):
                    preview_output = gr.HTML('<div></div>')
                    extract_btn = gr.Button('Extract GLB')
                with gr.Step('Extract', id=1):
                    glb_output = gr.Model3D(label='Extracted GLB')
                    download_btn = gr.DownloadButton(label='Download GLB')
        with gr.Column(scale=1):
            example_dir = os.path.join(TMP_DIR, 'examples')
            os.makedirs(example_dir, exist_ok=True)
            example = os.path.join(example_dir, 'a.png')
            Image.new('RGBA', (8, 8), (255, 0, 0, 255)).save(example)
            examples = gr.Examples(examples=[example], inputs=[image_prompt], fn=preprocess_image,
                                   outputs=[image_prompt], run_on_click=True)

    output_buf = gr.State()

    demo.load(start_session)
    demo.unload(end_session)

    image_prompt.upload(preprocess_image, inputs=[image_prompt], outputs=[image_prompt])

    generate_btn.click(get_seed, inputs=[randomize_seed, seed], outputs=[seed]).then(
        lambda: gr.Walkthrough(selected=0), outputs=walkthrough
    ).then(
        image_to_3d,
        inputs=[image_prompt, seed, resolution,
                ss_guidance_strength, ss_guidance_rescale, ss_sampling_steps, ss_rescale_t,
                shape_slat_guidance_strength, shape_slat_guidance_rescale, shape_slat_sampling_steps,
                shape_slat_rescale_t,
                tex_slat_guidance_strength, tex_slat_guidance_rescale, tex_slat_sampling_steps,
                tex_slat_rescale_t],
        outputs=[output_buf, preview_output],
    )

    extract_btn.click(lambda: gr.Walkthrough(selected=1), outputs=walkthrough).then(
        extract_glb, inputs=[output_buf, decimation_target, texture_size], outputs=[glb_output, download_btn],
    )


if __name__ == '__main__':
    os.makedirs(TMP_DIR, exist_ok=True)
    demo.launch(server_name='127.0.0.1', server_port=int(sys.argv[1]) if len(sys.argv) > 1 else 7860)
