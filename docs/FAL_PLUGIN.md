# fal.ai plugin

`deda.plugins.fal` runs hosted fal.ai models from Dedaverse (Tools > fal, or the **fal** service tile).

## Setup

```
pip install -e ".[fal]"
set FAL_KEY=<your fal.ai key>      # or type it into the window; it is never saved
```

## Tasks and models

Choose a task and the plugin recommends a model; pick another or change **Prefer** (fast / balanced / best quality).

| Task | Models (default first) | Inputs |
|---|---|---|
| Image from text | FLUX.1 [dev], FLUX.1 [schnell] (fast), FLUX1.1 [pro] (quality) | prompt, direction |
| Image from image | FLUX.1 [dev] image to image, FLUX general image to image (takes a reference image) | prompt, source image, optional reference |
| Edit an image | FLUX.1 Kontext [pro] | instruction, source image |
| 3D mesh from image | TRELLIS (GLB), Hunyuan3D 2.1 | source image |

Art direction: the **Direction** text is added to the prompt for every model. A **reference image** (moodboard, sketch, or
a snapshot with annotations on it) is sent to models that take one. **Use Viewer Notes...** loads a note saved with
*Save Notes* in the Dedaverse viewer: its text becomes the direction and its `snapshot_*.png` the reference image.

Results are downloaded to the output folder (default `~/dedaverse/fal`) and never overwrite earlier files.
Meshes come back as `.glb`; open them in the Dedaverse viewer's import flow or any DCC.

## Adding or changing models

Models are described in code (`_models.py`). To add one without editing code, create `~/.dedaverse/fal/models.json`
(or set `DEDAVERSE_FAL_MODELS` to another file), a list of objects. An entry with the same `endpoint` as a built-in
replaces it.

```json
[{
  "endpoint": "fal-ai/flux-lora",
  "label": "FLUX with LoRA",
  "task": "text_to_image",
  "description": "Text to image with a custom LoRA.",
  "prompt_arg": "prompt",
  "output_field": "images",
  "output_kind": "image",
  "speed": "balanced",
  "params": [
    {"name": "num_inference_steps", "label": "Steps", "kind": "int", "default": 28, "minimum": 1, "maximum": 50},
    {"name": "guidance_scale", "label": "Guidance", "kind": "float", "default": 3.5, "minimum": 1, "maximum": 20}
  ]
}]
```

`task` is `text_to_image`, `image_to_image`, `image_edit` or `image_to_3d`; use `image_arg` / `reference_arg` /
`negative_prompt_arg` to name the model's input arguments, and `output_field` for where the files are in the response.

## From code

```python
from deda.plugins import fal
model = fal.recommend(fal.IMAGE_TO_3D)
request = fal.FalRequest(model, image='chair.png', output_dir='out')
result = fal.FalClient().run(request, on_status=print)
print(result.paths)
```
