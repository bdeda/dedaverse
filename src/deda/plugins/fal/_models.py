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
"""The fal.ai models Dedaverse knows how to drive, grouped by task, with a recommender.

Each :class:`FalModel` says which endpoint to call, which input argument takes the image, which output
field holds the result, and which parameters are worth exposing. Endpoint schemas are fal.ai's; to add or
change a model without editing code, put entries in ``~/.dedaverse/fal/models.json`` (see
:func:`load_user_models`) or point ``DEDAVERSE_FAL_MODELS`` at a JSON file.
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

ENV_MODELS_FILE = 'DEDAVERSE_FAL_MODELS'
USER_MODELS_FILE = Path.home() / '.dedaverse' / 'fal' / 'models.json'

TEXT_TO_IMAGE = 'text_to_image'
IMAGE_TO_IMAGE = 'image_to_image'
IMAGE_EDIT = 'image_edit'
IMAGE_TO_3D = 'image_to_3d'
TEXT_TO_MUSIC = 'text_to_music'
SOUND_EFFECT = 'sound_effect'
TEXT_TO_SPEECH = 'text_to_speech'
VIDEO_TO_AUDIO = 'video_to_audio'

#: Task keys in the order the UI shows them, with their labels.
TASKS = {
    TEXT_TO_IMAGE: 'Image from text',
    IMAGE_TO_IMAGE: 'Image from image (restyle / art direction)',
    IMAGE_EDIT: 'Edit an image with instructions',
    IMAGE_TO_3D: '3D mesh from image',
    TEXT_TO_MUSIC: 'Music from text',
    SOUND_EFFECT: 'Sound effect from text',
    TEXT_TO_SPEECH: 'Speech from text',
    VIDEO_TO_AUDIO: 'Sound for a video',
}

IMAGE = 'image'
MESH = 'mesh'
AUDIO = 'audio'
VIDEO = 'video'
OUTPUT_KINDS = (IMAGE, MESH, AUDIO, VIDEO)


@dataclass(frozen=True)
class Param:
    """One tunable input of a model.

    Attributes:
        name: The fal.ai argument name.
        label: Text for the UI.
        kind: ``int``, ``float``, ``bool``, ``choice`` or ``text``.
        default: Value used when the user does not change it (None leaves the argument out).
        minimum: Lowest allowed value for ``int``/``float``.
        maximum: Highest allowed value for ``int``/``float``.
        choices: The allowed values for ``choice``.
        help: A one-line explanation.
    """

    name: str
    label: str
    kind: str
    default: object = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple = ()
    help: str = ''

    def coerce(self, value):
        """Return ``value`` converted to this parameter's type and clamped to its range."""
        if self.kind == 'bool':
            return bool(value)
        if self.kind == 'text':
            return str(value)
        if self.kind == 'choice':
            return value if value in self.choices else self.default
        number = int(value) if self.kind == 'int' else float(value)
        if self.minimum is not None:
            number = max(self.minimum, number)
        if self.maximum is not None:
            number = min(self.maximum, number)
        return number


@dataclass(frozen=True)
class FalModel:
    """A fal.ai endpoint and how to feed and read it.

    Attributes:
        endpoint: The application id, e.g. ``fal-ai/flux/dev``.
        label: Short name for the UI.
        task: One of :data:`TASKS`.
        description: What it is good for.
        prompt_arg: Name of the text prompt argument, or None if the model takes none.
        image_arg: Name of the argument that takes the source image URL, or None for text-only models.
        video_arg: Name of the argument that takes a source video URL, or None.
        reference_arg: Name of an argument that takes a second, reference image (art direction, a markup or
            sketch), or None if the model has no such input.
        negative_prompt_arg: Name of the negative prompt argument, or None.
        output_field: The result field holding the files (a list for images, a single file for meshes).
        output_kind: ``image``, ``mesh``, ``audio`` or ``video``.
        direction_in_prompt: Whether written art direction may be added to the prompt. False for models
            that speak or sing their text verbatim.
        params: Tunable inputs.
        speed: ``fast``, ``balanced`` or ``quality``; used by the recommender.
        notes: Anything to know before using it (cost, licence, status).
    """

    endpoint: str
    label: str
    task: str
    description: str
    prompt_arg: str | None = 'prompt'
    image_arg: str | None = None
    video_arg: str | None = None
    reference_arg: str | None = None
    negative_prompt_arg: str | None = None
    output_field: str = 'images'
    output_kind: str = IMAGE
    direction_in_prompt: bool = True
    params: tuple = ()
    speed: str = 'balanced'
    notes: str = ''

    def defaults(self) -> dict:
        """The default value of every parameter that has one."""
        return {p.name: p.default for p in self.params if p.default is not None}

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)


_SIZES = ('square_hd', 'square', 'portrait_4_3', 'portrait_16_9', 'landscape_4_3', 'landscape_16_9')
_SEED = Param('seed', 'Seed', 'int', None, 0, 2 ** 31 - 1, help='Same seed and prompt give the same result.')
_COUNT = Param('num_images', 'Images', 'int', 1, 1, 4)
_FORMAT = Param('output_format', 'Format', 'choice', 'png', choices=('png', 'jpeg'))
_GUIDANCE = Param('guidance_scale', 'Guidance', 'float', 3.5, 1.0, 20.0, help='How closely to follow the prompt.')
_SIZE = Param('image_size', 'Size', 'choice', 'landscape_4_3', choices=_SIZES)

BUILTIN_MODELS = (
    FalModel(
        'fal-ai/flux/schnell', 'FLUX.1 [schnell]', TEXT_TO_IMAGE,
        'Very fast text to image. Good for thumbnails and exploring ideas.',
        params=(_SIZE, Param('num_inference_steps', 'Steps', 'int', 4, 1, 12), _COUNT, _SEED, _FORMAT),
        speed='fast'),
    FalModel(
        'fal-ai/flux/dev', 'FLUX.1 [dev]', TEXT_TO_IMAGE,
        'Balanced text to image with good prompt adherence. The default for concept art.',
        params=(_SIZE, Param('num_inference_steps', 'Steps', 'int', 28, 1, 50), _GUIDANCE, _COUNT, _SEED, _FORMAT),
        speed='balanced',
        notes='FLUX.1 [dev] is licensed for non-commercial use unless you hold a commercial licence.'),
    FalModel(
        'fal-ai/flux-pro/v1.1', 'FLUX1.1 [pro]', TEXT_TO_IMAGE,
        'Highest quality text to image. Use for final looks.',
        params=(_SIZE, _COUNT, _SEED, _FORMAT), speed='quality'),
    FalModel(
        'fal-ai/flux/dev/image-to-image', 'FLUX.1 [dev] image to image', IMAGE_TO_IMAGE,
        'Restyle an image from a prompt. Strength sets how far it may drift from the source.',
        image_arg='image_url',
        params=(Param('strength', 'Strength', 'float', 0.85, 0.0, 1.0, help='0 keeps the source, 1 remakes it.'),
                Param('num_inference_steps', 'Steps', 'int', 40, 1, 50), _GUIDANCE, _COUNT, _SEED, _FORMAT),
        speed='balanced'),
    FalModel(
        'fal-ai/flux-general/image-to-image', 'FLUX general image to image', IMAGE_TO_IMAGE,
        'Image to image that also takes a reference image, to steer style or look from a moodboard, '
        'sketch or markup.',
        image_arg='image_url', reference_arg='reference_image_url', negative_prompt_arg='negative_prompt',
        params=(Param('strength', 'Strength', 'float', 0.85, 0.0, 1.0),
                Param('reference_strength', 'Reference strength', 'float', 0.65, 0.0, 1.0,
                      help='How strongly the reference image steers the result.'),
                Param('num_inference_steps', 'Steps', 'int', 28, 1, 50), _GUIDANCE, _COUNT, _SEED, _FORMAT),
        speed='quality'),
    FalModel(
        'fal-ai/flux-pro/kontext', 'FLUX.1 Kontext [pro]', IMAGE_EDIT,
        'Edit an image by describing the change ("make the jacket red", "add rain"). Keeps the rest intact.',
        image_arg='image_url',
        params=(_GUIDANCE, _COUNT, _SEED, _FORMAT,
                Param('aspect_ratio', 'Aspect', 'choice', None,
                      choices=('21:9', '16:9', '4:3', '3:2', '1:1', '2:3', '3:4', '9:16', '9:21'))),
        speed='quality'),
    FalModel(
        'fal-ai/trellis', 'TRELLIS (image to 3D)', IMAGE_TO_3D,
        'Textured 3D mesh (GLB) from a single image. Works best on one object on a plain background.',
        prompt_arg=None, image_arg='image_url', output_field='model_mesh', output_kind=MESH,
        params=(Param('ss_guidance_strength', 'Structure guidance', 'float', 7.5, 0.0, 10.0),
                Param('ss_sampling_steps', 'Structure steps', 'int', 12, 1, 50),
                Param('slat_guidance_strength', 'Detail guidance', 'float', 3.0, 0.0, 10.0),
                Param('slat_sampling_steps', 'Detail steps', 'int', 12, 1, 50),
                Param('mesh_simplify', 'Mesh simplify', 'float', 0.95, 0.0, 1.0,
                      help='Higher removes more triangles.'),
                Param('texture_size', 'Texture size', 'choice', 1024, choices=(512, 1024, 2048)), _SEED),
        speed='balanced'),
    FalModel(
        'fal-ai/hunyuan3d-v21', 'Hunyuan3D 2.1 (image to 3D)', IMAGE_TO_3D,
        'Image to 3D mesh with an optional PBR textured result. Textured output costs about three times a '
        'white mesh.',
        prompt_arg=None, image_arg='input_image_url', output_field='model_glb', output_kind=MESH,
        params=(Param('textured_mesh', 'Textured', 'bool', False),
                Param('num_inference_steps', 'Steps', 'int', 50, 1, 100),
                Param('guidance_scale', 'Guidance', 'float', 7.5, 1.0, 20.0),
                Param('octree_resolution', 'Octree resolution', 'int', 256, 64, 512), _SEED),
        speed='quality', notes='fal.ai marks this endpoint deprecated; use it only if TRELLIS does not suit.'),
    FalModel(
        'fal-ai/stable-audio-25/text-to-audio', 'Stable Audio 2.5', TEXT_TO_MUSIC,
        'Music and ambience from a text description, up to about three minutes. Name genre, instruments, mood and tempo.',
        output_field='audio', output_kind=AUDIO,
        params=(Param('seconds_total', 'Length (s)', 'int', 30, 1, 190),
                Param('num_inference_steps', 'Steps', 'int', 8, 1, 50),
                Param('guidance_scale', 'Guidance', 'float', 1.0, 0.0, 20.0), _SEED),
        speed='balanced'),
    FalModel(
        'fal-ai/lyria2', 'Google Lyria 2', TEXT_TO_MUSIC,
        'High fidelity instrumental music: 48 kHz WAV, 30 seconds per clip.',
        negative_prompt_arg='negative_prompt', output_field='audio', output_kind=AUDIO,
        params=(_SEED,), speed='quality'),
    FalModel(
        'fal-ai/elevenlabs/sound-effects/v2', 'ElevenLabs sound effects', SOUND_EFFECT,
        'Sound effects from a description ("heavy wooden door creaks open"). Can loop smoothly.',
        prompt_arg='text', output_field='audio', output_kind=AUDIO,
        params=(Param('duration_seconds', 'Length (s)', 'float', None, 0.5, 22.0),
                Param('prompt_influence', 'Prompt influence', 'float', 0.3, 0.0, 1.0,
                      help='Higher means less variation.'),
                Param('loop', 'Loop', 'bool', False),
                Param('output_format', 'Format', 'choice', 'mp3_44100_128',
                      choices=('mp3_44100_128', 'mp3_44100_192', 'mp3_44100_64', 'pcm_44100', 'pcm_48000',
                               'opus_48000_128'))),
        speed='balanced'),
    FalModel(
        'fal-ai/mmaudio-v2/text-to-audio', 'MMAudio (text to audio)', SOUND_EFFECT,
        'Sound effects and ambience from a description, with a negative prompt.',
        negative_prompt_arg='negative_prompt', output_field='audio', output_kind=AUDIO,
        params=(Param('duration', 'Length (s)', 'float', 8.0, 1.0, 30.0),
                Param('num_steps', 'Steps', 'int', 25, 1, 100),
                Param('cfg_strength', 'Prompt strength', 'float', 4.5, 0.0, 20.0), _SEED),
        speed='fast'),
    FalModel(
        'fal-ai/kokoro/american-english', 'Kokoro (American English speech)', TEXT_TO_SPEECH,
        'Fast, natural text to speech in American English. Good for scratch dialogue and narration.',
        prompt_arg='prompt', output_field='audio', output_kind=AUDIO, direction_in_prompt=False,
        params=(Param('voice', 'Voice', 'choice', 'af_heart', choices=(
                    'af_heart', 'af_alloy', 'af_aoede', 'af_bella', 'af_jessica', 'af_kore', 'af_nicole', 'af_nova',
                    'af_river', 'af_sarah', 'af_sky', 'am_adam', 'am_echo', 'am_eric', 'am_fenrir', 'am_liam',
                    'am_michael', 'am_onyx', 'am_puck', 'am_santa')),
                Param('speed', 'Speed', 'float', 1.0, 0.5, 2.0)),
        speed='fast'),
    FalModel(
        'fal-ai/elevenlabs/tts/turbo-v2.5', 'ElevenLabs Turbo v2.5 (speech)', TEXT_TO_SPEECH,
        'Expressive multilingual text to speech with named voices.',
        prompt_arg='text', output_field='audio', output_kind=AUDIO, direction_in_prompt=False,
        params=(Param('voice', 'Voice', 'text', 'Rachel', help='An ElevenLabs voice name, such as Rachel or Aria.'),
                Param('stability', 'Stability', 'float', 0.5, 0.0, 1.0),
                Param('similarity_boost', 'Similarity', 'float', 0.75, 0.0, 1.0),
                Param('speed', 'Speed', 'float', 1.0, 0.7, 1.2),
                Param('language_code', 'Language code', 'text', None, help='ISO 639-1, such as en or fr.')),
        speed='quality'),
    FalModel(
        'fal-ai/mmaudio-v2', 'MMAudio (sound for a video)', VIDEO_TO_AUDIO,
        'Adds synchronised sound to a video from a description. The result is a video with the new audio.',
        video_arg='video_url', negative_prompt_arg='negative_prompt', output_field='video', output_kind=VIDEO,
        params=(Param('duration', 'Length (s)', 'float', 8.0, 1.0, 30.0),
                Param('num_steps', 'Steps', 'int', 25, 1, 100),
                Param('cfg_strength', 'Prompt strength', 'float', 4.5, 0.0, 20.0), _SEED),
        speed='balanced'),
)

#: What the recommender prefers for each task when no speed is asked for (or none matches).
_DEFAULT_PICK = {
    TEXT_TO_IMAGE: 'fal-ai/flux/dev',
    IMAGE_TO_IMAGE: 'fal-ai/flux/dev/image-to-image',
    IMAGE_EDIT: 'fal-ai/flux-pro/kontext',
    IMAGE_TO_3D: 'fal-ai/trellis',
    TEXT_TO_MUSIC: 'fal-ai/stable-audio-25/text-to-audio',
    SOUND_EFFECT: 'fal-ai/elevenlabs/sound-effects/v2',
    TEXT_TO_SPEECH: 'fal-ai/kokoro/american-english',
    VIDEO_TO_AUDIO: 'fal-ai/mmaudio-v2',
}


_DEFAULT_OUTPUT_FIELD = {IMAGE: 'images', MESH: 'model_mesh', AUDIO: 'audio', VIDEO: 'video'}


def _param_from_dict(data: dict) -> Param:
    return Param(
        name=data['name'], label=data.get('label', data['name']), kind=data.get('kind', 'float'),
        default=data.get('default'), minimum=data.get('minimum'), maximum=data.get('maximum'),
        choices=tuple(data.get('choices', ())), help=data.get('help', ''))


def model_from_dict(data: dict) -> FalModel:
    """Build a model from the JSON form used by the user models file.

    Raises:
        KeyError: If ``endpoint``, ``label`` or ``task`` is missing.
        ValueError: If ``task`` is not a known task or ``output_kind`` is not ``image`` or ``mesh``.
    """
    task = data['task']
    if task not in TASKS:
        raise ValueError(f'unknown task {task!r}; expected one of {sorted(TASKS)}')
    kind = data.get('output_kind', IMAGE)
    if kind not in OUTPUT_KINDS:
        raise ValueError(f'output_kind must be one of {OUTPUT_KINDS}, not {kind!r}')
    return FalModel(
        endpoint=data['endpoint'], label=data['label'], task=task, description=data.get('description', ''),
        prompt_arg=data.get('prompt_arg', 'prompt'), image_arg=data.get('image_arg'), video_arg=data.get('video_arg'),
        reference_arg=data.get('reference_arg'), negative_prompt_arg=data.get('negative_prompt_arg'),
        output_field=data.get('output_field', _DEFAULT_OUTPUT_FIELD[kind]), output_kind=kind,
        direction_in_prompt=data.get('direction_in_prompt', True),
        params=tuple(_param_from_dict(p) for p in data.get('params', ())), speed=data.get('speed', 'balanced'),
        notes=data.get('notes', ''))


def load_user_models(path: str | Path | None = None) -> list[FalModel]:
    """Read extra models from a JSON file (a list of objects, see :func:`model_from_dict`).

    Args:
        path: The file. Defaults to ``DEDAVERSE_FAL_MODELS``, then ``~/.dedaverse/fal/models.json``.

    Returns:
        The models in the file; invalid entries are skipped with a warning. An absent file is not an error.
    """
    file = Path(path or os.environ.get(ENV_MODELS_FILE) or USER_MODELS_FILE)
    if not file.is_file():
        return []
    try:
        entries = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, ValueError) as err:
        log.warning(f'Could not read fal models from {file}: {err}')
        return []
    models = []
    for entry in entries if isinstance(entries, list) else []:
        try:
            models.append(model_from_dict(entry))
        except (KeyError, ValueError, TypeError) as err:
            log.warning(f'Skipping invalid fal model entry in {file}: {err!r}')
    return models


def all_models(user_models_file: str | Path | None = None) -> list[FalModel]:
    """The built-in models plus the user's; a user entry replaces a built-in one with the same endpoint."""
    merged = {m.endpoint: m for m in BUILTIN_MODELS}
    for model in load_user_models(user_models_file):
        merged[model.endpoint] = model
    return list(merged.values())


def models_for(task: str, models: list[FalModel] | None = None) -> list[FalModel]:
    """The models that do ``task``, in registry order."""
    return [m for m in (models if models is not None else all_models()) if m.task == task]


def task_for(has_prompt: bool, has_image: bool, want_3d: bool = False, edit: bool = False) -> str:
    """Pick the task from what the user supplied.

    Args:
        has_prompt: A text prompt was entered.
        has_image: A source image was supplied.
        want_3d: The user wants a mesh.
        edit: The prompt is an instruction to change the image rather than a description of a new one.

    Raises:
        ValueError: If the inputs cannot lead to any task (no image and no prompt, or 3D without an image).
    """
    if want_3d:
        if not has_image:
            raise ValueError('3D from an image needs a source image')
        return IMAGE_TO_3D
    if has_image and has_prompt:
        return IMAGE_EDIT if edit else IMAGE_TO_IMAGE
    if has_image:
        raise ValueError('Add a prompt to say what to do with the image')
    if has_prompt:
        return TEXT_TO_IMAGE
    raise ValueError('Enter a prompt or choose a source image')


def recommend(task: str, speed: str | None = None, has_reference: bool = False,
              models: list[FalModel] | None = None) -> FalModel:
    """Choose the model to use for ``task``.

    Args:
        task: One of :data:`TASKS`.
        speed: ``fast``, ``balanced`` or ``quality`` to prefer a model of that speed, or None for the task default.
        has_reference: A reference image (art direction, markup, sketch) is supplied: prefer a model that takes one.
        models: The registry to choose from; defaults to :func:`all_models`.

    Raises:
        ValueError: If no model does ``task``.
    """
    candidates = models_for(task, models)
    if not candidates:
        raise ValueError(f'No fal model is registered for task {task!r}')
    if has_reference:
        with_reference = [m for m in candidates if m.reference_arg]
        if with_reference:
            candidates = with_reference
    if speed:
        matching = [m for m in candidates if m.speed == speed]
        if matching:
            return matching[0]
    preferred = [m for m in candidates if m.endpoint == _DEFAULT_PICK.get(task)]
    return preferred[0] if preferred else candidates[0]
