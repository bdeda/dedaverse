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
"""Shared image loading for formats Qt can't decode natively: HEIC/HEIF and camera RAW.

Standard formats (JPEG, PNG, TIFF, BMP, WebP) are handled directly via QImageReader and
don't need the optional dependencies below. HEIC uses pillow-heif; RAW formats (ARW, CR2,
NEF, DNG, etc.) use rawpy (LibRaw). Both are the "raw_formats" extra -- install with
pip install -e ".[raw_formats]". Call is_available() to check before relying on them.

Two decode paths are provided per format: load_preview_qimage() for fast thumbnail-grid
display (uses a RAW file's embedded preview JPEG instead of a full demosaic where possible)
and load_full_qimage() for full-quality viewing/upscaling (full demosaic for RAW).
"""
__all__ = [
    'HEIC_EXTENSIONS',
    'RAW_EXTENSIONS',
    'STANDARD_EXTENSIONS',
    'SUPPORTED_EXTENSIONS',
    'is_available',
    'is_image_file',
    'load_full_qimage',
    'load_preview_qimage',
    'read_image_size',
]

import logging
from pathlib import Path

from PySide6 import QtCore, QtGui

log = logging.getLogger(__name__)

STANDARD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.webp'}
HEIC_EXTENSIONS = {'.heic', '.heif'}
RAW_EXTENSIONS = {'.arw', '.cr2', '.cr3', '.nef', '.dng', '.orf', '.rw2', '.raf', '.pef'}
SUPPORTED_EXTENSIONS = STANDARD_EXTENSIONS | HEIC_EXTENSIONS | RAW_EXTENSIONS

_heif_opener_registered = False


def is_image_file(path: Path) -> bool:
    """Return True if path's extension is one this module (or plain QImageReader) can read."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_available() -> tuple[bool, str]:
    """Return (True, '') if pillow-heif and rawpy are importable.

    Standard formats work regardless; this only gates HEIC/RAW files.
    """
    try:
        import pillow_heif  # noqa: F401
        import rawpy  # noqa: F401
    except ImportError as err:
        return False, (
            'HEIC and camera RAW (ARW, CR2, NEF, DNG, ...) support requires the optional '
            '"raw_formats" extras.\nInstall with:  pip install -e ".[raw_formats]"\n'
            f'(missing package: {err.name})'
        )
    return True, ''


def _swaps_dimensions(reader: QtGui.QImageReader) -> bool:
    """True if the file's EXIF orientation involves a 90-degree-family rotation.

    QImageReader.size() always reports the raw, pre-transform pixel grid -- setAutoTransform
    does not affect it, only .read() actually applies the rotation. Any code that needs the
    correctly-oriented (as-displayed) dimensions without a full decode has to detect and
    apply this swap itself.
    """
    return bool(reader.transformation() & QtGui.QImageIOHandler.Transformation.TransformationRotate90)


def _register_heif_opener() -> None:
    global _heif_opener_registered
    if _heif_opener_registered:
        return
    import pillow_heif
    pillow_heif.register_heif_opener()
    _heif_opener_registered = True


def _pil_to_qimage(img) -> QtGui.QImage:
    img = img.convert('RGB')
    data = img.tobytes('raw', 'RGB')
    qimage = QtGui.QImage(data, img.width, img.height, img.width * 3, QtGui.QImage.Format.Format_RGB888)
    return qimage.copy()  # detach from the Python bytes buffer before it goes out of scope


def _jpeg_bytes_to_qimage(data: bytes) -> QtGui.QImage:
    """Decode JPEG bytes (e.g. a RAW file's embedded preview) respecting EXIF orientation."""
    buf = QtCore.QBuffer()
    buf.setData(data)
    buf.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    reader = QtGui.QImageReader(buf, b'JPG')
    reader.setAutoTransform(True)
    return reader.read()


def _heic_size(path: Path) -> tuple[int, int] | None:
    _register_heif_opener()
    import pillow_heif
    heif_file = pillow_heif.open_heif(str(path), convert_hdr_to_8bit=False)
    if heif_file is None:
        return None
    return heif_file.size


def _heic_full(path: Path) -> QtGui.QImage:
    _register_heif_opener()
    from PIL import Image, ImageOps
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return _pil_to_qimage(img)


def _heic_preview(path: Path, max_size: int) -> QtGui.QImage:
    _register_heif_opener()
    from PIL import Image, ImageOps
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return _pil_to_qimage(img)


def _raw_size(path: Path) -> tuple[int, int] | None:
    import rawpy
    with rawpy.imread(str(path)) as raw:
        sizes = raw.sizes  # .width/.height already account for the sensor's flip/orientation
        return sizes.width, sizes.height


def _raw_full(path: Path) -> QtGui.QImage:
    import numpy as np
    import rawpy
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=8, no_auto_bright=False)
    rgb = np.ascontiguousarray(rgb)
    height, width, _ = rgb.shape
    qimage = QtGui.QImage(rgb.data, width, height, width * 3, QtGui.QImage.Format.Format_RGB888)
    return qimage.copy()


def _raw_preview(path: Path, max_size: int) -> QtGui.QImage:
    import rawpy
    with rawpy.imread(str(path)) as raw:
        try:
            thumb = raw.extract_thumb()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            thumb = None
        if thumb is not None and thumb.format == rawpy.ThumbFormat.JPEG:
            image = _jpeg_bytes_to_qimage(thumb.data)
            if not image.isNull():
                return image.scaled(
                    max_size, max_size,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
    # No usable embedded thumbnail (or it failed to decode) -- fall back to a full demosaic.
    image = _raw_full(path)
    if image.isNull():
        return image
    return image.scaled(
        max_size, max_size,
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )


def read_image_size(path) -> tuple[int, int] | None:
    """Return (width, height) in pixels as displayed (post EXIF/RAW orientation), or None."""
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext in HEIC_EXTENSIONS:
            return _heic_size(path)
        if ext in RAW_EXTENSIONS:
            return _raw_size(path)
    except ImportError:
        log.warning(f'Cannot read size of {path.name}: raw_formats extras not installed.')
        return None
    except Exception as err:
        log.error(f'Failed to read size of {path}: {err}')
        return None

    reader = QtGui.QImageReader(str(path))
    reader.setAutoTransform(True)
    raw_size = reader.size()
    if not raw_size.isValid() or raw_size.width() <= 0 or raw_size.height() <= 0:
        return None
    if _swaps_dimensions(reader):
        return raw_size.height(), raw_size.width()
    return raw_size.width(), raw_size.height()


def load_full_qimage(path) -> QtGui.QImage:
    """Load path at full quality/resolution, respecting EXIF/RAW orientation.

    Returns a null QImage if the file can't be read, or its format needs raw_formats extras
    that aren't installed (call is_available() first to tell the two cases apart).
    """
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext in HEIC_EXTENSIONS:
            return _heic_full(path)
        if ext in RAW_EXTENSIONS:
            return _raw_full(path)
    except ImportError:
        log.warning(f'Cannot read {path.name}: raw_formats extras not installed.')
        return QtGui.QImage()
    except Exception as err:
        log.error(f'Failed to read {path}: {err}')
        return QtGui.QImage()

    reader = QtGui.QImageReader(str(path))
    reader.setAutoTransform(True)
    return reader.read()


def load_preview_qimage(path, max_size: int = 160) -> QtGui.QImage:
    """Load a downscaled preview of path, suitable for a thumbnail grid.

    For RAW files this uses the camera's embedded preview JPEG when available, which is far
    faster than a full demosaic. Falls back to load_full_qimage() + scaling otherwise.
    """
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext in HEIC_EXTENSIONS:
            return _heic_preview(path, max_size)
        if ext in RAW_EXTENSIONS:
            return _raw_preview(path, max_size)
    except ImportError:
        log.warning(f'Cannot read {path.name}: raw_formats extras not installed.')
        return QtGui.QImage()
    except Exception as err:
        log.error(f'Failed to read {path}: {err}')
        return QtGui.QImage()

    reader = QtGui.QImageReader(str(path))
    reader.setAutoTransform(True)
    raw_size = reader.size()
    if raw_size.isValid() and raw_size.width() > 0 and raw_size.height() > 0:
        swapped = _swaps_dimensions(reader)
        # Scale in as-displayed terms, then convert back to raw-grid terms: setScaledSize()
        # is applied before the auto-transform rotates the decoded result (see _swaps_dimensions).
        display_size = QtCore.QSize(raw_size.height(), raw_size.width()) if swapped else raw_size
        scaled_display = display_size.scaled(max_size, max_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        scaled_raw = (
            QtCore.QSize(scaled_display.height(), scaled_display.width()) if swapped else scaled_display
        )
        reader.setScaledSize(scaled_raw)
    return reader.read()
