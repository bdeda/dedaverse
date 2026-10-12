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
"""Spandrel-based upscaling (chaiNNer's model-loading backend), tiled to bound GPU/CPU memory use.

Model weights are downloaded from Hugging Face on first use and cached by huggingface_hub.
Each entry in UPSCALE_MODELS can be overridden with a local .pth path via its env_var, to
skip the download or swap in a different checkpoint for the same architecture.

Both models currently registered are ESRGAN-family (RRDBNet) checkpoints trained BasicSR-style
on BGR images -- see the channel-swap in upscale_image(). A future architecture trained on RGB
would need a per-model channel_order flag added to UPSCALE_MODELS; not needed yet.
"""
__all__ = ['DEFAULT_UPSCALE_MODEL', 'UPSCALE_MODELS', 'is_available', 'upscale_image']

import logging
import math
import os
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# Curated from chaiNNer/spandrel's supported architectures (spandrel is chaiNNer's own
# model-loading library) and OpenModelDB, the community model index chaiNNer points users to.
UPSCALE_MODELS = {
    'ultrasharp': {
        'label': '4x-UltraSharp (sharp/detail)',
        'repo_id': 'Shandypur/ESRGAN-4x-UltraSharp',
        'filename': '4x-UltraSharp.pth',
        'env_var': 'DIGICAM_ULTRASHARP_MODEL',
    },
    'realesrgan_x4plus': {
        'label': 'RealESRGAN x4plus (balanced/faithful)',
        'repo_id': 'alexgenovese/upscalers',
        'filename': 'RealESRGAN_x4plus.pth',
        'env_var': 'DIGICAM_REALESRGAN_X4PLUS_MODEL',
    },
}
DEFAULT_UPSCALE_MODEL = 'ultrasharp'

_model_cache: dict[str, object] = {}  # model_key -> loaded spandrel ImageModelDescriptor


def is_available() -> tuple[bool, str]:
    """Return (True, '') if the optional upscaling dependencies are importable.

    Otherwise returns (False, <install hint>) so the UI can show the user what to run.
    """
    try:
        import torch  # noqa: F401
        import spandrel  # noqa: F401
        import huggingface_hub  # noqa: F401
    except ImportError as err:
        return False, (
            'Upscaling requires the optional "upscale" extras (torch, spandrel, huggingface_hub).\n'
            'Install with:  pip install -e ".[upscale]"\n'
            f'(missing package: {err.name})'
        )
    return True, ''


def _model_path(model_key: str) -> Path:
    entry = UPSCALE_MODELS[model_key]
    override = os.environ.get(entry['env_var'])
    if override and Path(override).is_file():
        return Path(override)
    from huggingface_hub import hf_hub_download
    # Weights come from the fixed repos in UPSCALE_MODELS; no pinned revisions are known.
    return Path(hf_hub_download(repo_id=entry['repo_id'], filename=entry['filename']))  # nosec B615


def _load_model(model_key: str):
    if model_key not in UPSCALE_MODELS:
        raise KeyError(f'Unknown upscale model {model_key!r}. Known models: {list(UPSCALE_MODELS)}')
    if model_key in _model_cache:
        return _model_cache[model_key]

    import torch
    from spandrel import ImageModelDescriptor, ModelLoader

    model_path = _model_path(model_key)
    model = ModelLoader().load_from_file(str(model_path))
    if not isinstance(model, ImageModelDescriptor):
        raise TypeError(f'{model_path} is not a single-image upscale model.')

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device).eval()
    log.info(f'Loaded {model_path.name} ({model.architecture}) on {device}, scale={model.scale}x')
    _model_cache[model_key] = model
    return model


def upscale_image(
    image_path: Path,
    model_key: str = DEFAULT_UPSCALE_MODEL,
    tile_size: int = 512,
    tile_pad: int = 16,
    progress_cb: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
):
    """Upscale image_path with the given registered model, processing it in overlapping tiles.

    Tiling bounds GPU/CPU memory use for full-resolution photos: each tile is padded with
    tile_pad pixels of neighboring context (for a cleaner result at the tile borders), run
    through the model, then only its central, non-padded region is pasted into the output.

    Args:
        image_path: Source image to upscale.
        model_key: Key into UPSCALE_MODELS selecting which model to run.
        tile_size: Width/height (in source-image pixels) of each tile fed to the model.
        tile_pad: Extra context (in source-image pixels) added around each tile.
        progress_cb: Optional callable(done_tiles, total_tiles), called after each tile.
        should_cancel: Optional callable() -> bool, checked before each tile.

    Returns:
        QtGui.QImage: The upscaled image, or None if should_cancel() returned True.

    """
    import numpy as np
    import torch
    from PySide6 import QtGui

    from deda.core._image_io import load_full_qimage

    model = _load_model(model_key)

    qimage = load_full_qimage(image_path)
    if qimage.isNull():
        raise ValueError(f'Could not read image: {image_path}')
    qimage = qimage.convertToFormat(QtGui.QImage.Format.Format_RGB888)

    width, height = qimage.width(), qimage.height()
    bytes_per_line = qimage.bytesPerLine()
    buf = np.frombuffer(qimage.constBits(), dtype=np.uint8, count=height * bytes_per_line)
    buf = buf.reshape((height, bytes_per_line))
    source = np.ascontiguousarray(buf[:, :width * 3].reshape((height, width, 3)))  # RGB, HWC, uint8

    scale = model.scale
    canvas = np.empty((height * scale, width * scale, 3), dtype=np.uint8)

    cols = math.ceil(width / tile_size)
    rows = math.ceil(height / tile_size)
    total_tiles = cols * rows
    done_tiles = 0

    for row in range(rows):
        y = row * tile_size
        tile_h = min(tile_size, height - y)
        for col in range(cols):
            if should_cancel and should_cancel():
                return None

            x = col * tile_size
            tile_w = min(tile_size, width - x)

            x0, y0 = max(0, x - tile_pad), max(0, y - tile_pad)
            x1, y1 = min(width, x + tile_w + tile_pad), min(height, y + tile_h + tile_pad)

            # ESRGAN old-arch models (incl. 4x-UltraSharp) are trained BasicSR-style on BGR.
            tile_bgr = np.ascontiguousarray(source[y0:y1, x0:x1, ::-1])
            tensor = torch.from_numpy(tile_bgr).to(model.dtype).div(255.0)
            tensor = tensor.permute(2, 0, 1).unsqueeze(0).to(model.device)

            with torch.no_grad():
                output = model(tensor)

            output = output.squeeze(0).clamp(0, 1).mul(255.0).round().to(torch.uint8)
            output_bgr = output.permute(1, 2, 0).cpu().numpy()
            output_rgb = output_bgr[:, :, ::-1]

            left_pad = (x - x0) * scale
            top_pad = (y - y0) * scale
            tile_out = output_rgb[top_pad:top_pad + tile_h * scale, left_pad:left_pad + tile_w * scale]

            canvas[y * scale:(y + tile_h) * scale, x * scale:(x + tile_w) * scale] = tile_out

            done_tiles += 1
            if progress_cb:
                progress_cb(done_tiles, total_tiles)

    canvas = np.ascontiguousarray(canvas)
    result = QtGui.QImage(canvas.data, canvas.shape[1], canvas.shape[0], canvas.shape[1] * 3,
                           QtGui.QImage.Format.Format_RGB888)
    return result.copy()
