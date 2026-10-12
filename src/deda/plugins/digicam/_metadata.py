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
"""Image sizing, aspect ratio, and print-size helpers for the digicam plugin."""
__all__ = [
    'DEFAULT_PRINT_DPI',
    'IMAGE_EXTENSIONS',
    'aspect_ratio_str',
    'format_print_size',
    'is_image_file',
    'iter_image_files',
    'load_thumbnail',
    'max_print_size_in',
    'read_image_size',
]

import math
from pathlib import Path

from PySide6 import QtGui

from deda.core._image_io import (
    SUPPORTED_EXTENSIONS as IMAGE_EXTENSIONS,
    is_image_file,
    load_preview_qimage,
    read_image_size,
)

DEFAULT_PRINT_DPI = 150


def iter_image_files(root: Path):
    """Yield every readable image file under root, recursively, in sorted order."""
    for path in sorted(root.rglob('*')):
        if path.is_file() and is_image_file(path):
            yield path


def load_thumbnail(path: Path, max_size: int = 160) -> QtGui.QPixmap:
    """Load a downscaled thumbnail for path, respecting EXIF/RAW orientation."""
    image = load_preview_qimage(path, max_size=max_size)
    if image.isNull():
        return QtGui.QPixmap()
    return QtGui.QPixmap.fromImage(image)


def aspect_ratio_str(width: int, height: int) -> str:
    """Return a simplified ratio like '3:2', falling back to a decimal ratio for odd crops."""
    if width <= 0 or height <= 0:
        return 'unknown'
    g = math.gcd(width, height)
    w, h = width // g, height // g
    if max(w, h) <= 50:
        return f'{w}:{h}'
    return f'{width / height:.2f}:1'


def max_print_size_in(width: int, height: int, dpi: int = DEFAULT_PRINT_DPI) -> tuple[float, float]:
    """Return the largest (width_in, height_in) that still meets dpi at full pixel count."""
    return width / dpi, height / dpi


def format_print_size(width: int, height: int, dpi: int = DEFAULT_PRINT_DPI) -> str:
    """Return a display string like '40.0" x 26.7" @ 150 DPI'."""
    w_in, h_in = max_print_size_in(width, height, dpi)
    return f'{w_in:.1f}" x {h_in:.1f}" @ {dpi} DPI'
