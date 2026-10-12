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
"""2D media for the viewer: images, image sequences and video files.

``open_media(path)`` returns a source for a file. A source reads one frame at a time as
a :class:`Frame` (a numpy array, so the viewer can apply exposure and channel display).

- Images and sequences are decoded with Qt (PNG, JPEG, TIFF, BMP, WebP, TGA, GIF) and, for
  EXR, with the optional ``OpenEXR`` package (``pip install -e ".[media]"``).
- Sequences are found from any one file in them (``shot.0001.exr`` finds the rest).
- Video uses ``QtMultimedia``.
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui

log = logging.getLogger(__name__)

QT_IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.tga', '.gif'})
EXR_EXTENSIONS = frozenset({'.exr'})
IMAGE_EXTENSIONS = QT_IMAGE_EXTENSIONS | EXR_EXTENSIONS
VIDEO_EXTENSIONS = frozenset({'.mp4', '.m4v', '.mov', '.avi', '.mkv', '.webm', '.wmv'})
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DEFAULT_FPS = 24.0
CHANNEL_MODES = ('rgba', 'rgb', 'r', 'g', 'b', 'a')


class MediaError(RuntimeError):
    """A media file could not be opened or decoded."""


def is_media_file(path) -> bool:
    """True if ``path`` has an extension the viewer can show as 2D media."""
    return Path(path).suffix.lower() in MEDIA_EXTENSIONS


@dataclass
class Frame:
    """One decoded frame.

    Attributes:
        pixels: RGBA, shape ``(height, width, 4)``. ``uint8`` for 8-bit sources and video,
            ``float32`` for 16-bit and EXR sources.
        linear: True when the values are scene-linear (EXR), so display applies the sRGB curve.
        info: Facts about the source for the HUD (``channels``, ``bit_depth``, ...).
    """
    pixels: np.ndarray
    linear: bool = False
    info: dict = field(default_factory=dict)

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])


# ---------------------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------------------

def _srgb_encode(linear: np.ndarray) -> np.ndarray:
    """The sRGB transfer function, for values in 0-1."""
    linear = np.clip(linear, 0.0, 1.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1.0 / 2.4) - 0.055)


def frame_to_qimage(frame: Frame, channel: str = 'rgba', exposure: float = 0.0) -> QtGui.QImage:
    """Turn a frame into a displayable 8-bit ``QImage`` (``Format_RGBA8888``, straight alpha).

    Args:
        frame: The frame to show.
        channel: One of :data:`CHANNEL_MODES`. ``rgb`` ignores alpha; ``r``/``g``/``b``/``a``
            show that channel as gray.
        exposure: Exposure in stops, applied before display. Only 8-bit frames that are
            shown unchanged skip the float path.

    Raises:
        ValueError: If ``channel`` is not a known mode.
    """
    if channel not in CHANNEL_MODES:
        raise ValueError(f'channel must be one of {CHANNEL_MODES}, not {channel!r}')
    pixels = frame.pixels
    if pixels.dtype == np.uint8 and channel == 'rgba' and exposure == 0.0 and not frame.linear:
        out = np.ascontiguousarray(pixels)
    else:
        rgba = pixels.astype(np.float32) / 255.0 if pixels.dtype == np.uint8 else pixels.astype(np.float32)
        if channel in ('r', 'g', 'b', 'a'):
            plane = rgba[..., 'rgba'.index(channel)]
            rgba = np.stack([plane, plane, plane, np.ones_like(plane)], axis=-1)
        elif channel == 'rgb':
            rgba = rgba.copy()
            rgba[..., 3] = 1.0
        if exposure:
            rgba = rgba.copy()
            rgba[..., :3] *= 2.0 ** exposure
        rgb = rgba[..., :3]
        rgb = _srgb_encode(rgb) if frame.linear else np.clip(rgb, 0.0, 1.0)
        out = np.empty(rgba.shape, dtype=np.uint8)
        out[..., :3] = (rgb * 255.0 + 0.5).astype(np.uint8)
        out[..., 3] = (np.clip(rgba[..., 3], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    height, width = out.shape[:2]
    image = QtGui.QImage(out.data, width, height, width * 4, QtGui.QImage.Format.Format_RGBA8888)
    return image.copy()  # detach from the numpy buffer


# ---------------------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------------------

def _qimage_to_pixels(image: QtGui.QImage) -> tuple[np.ndarray, int]:
    """Convert a ``QImage`` to an RGBA array. Returns ``(pixels, bit_depth)``."""
    sixteen = image.format() in (QtGui.QImage.Format.Format_RGBA64, QtGui.QImage.Format.Format_RGBX64,
                                 QtGui.QImage.Format.Format_RGBA64_Premultiplied,
                                 QtGui.QImage.Format.Format_RGB30, QtGui.QImage.Format.Format_BGR30)
    if sixteen:
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA64)
        width, height = image.width(), image.height()
        raw = np.frombuffer(image.constBits(), dtype=np.uint16)
        pixels = raw.reshape(height, image.bytesPerLine() // 8, 4)[:, :width].astype(np.float32) / 65535.0
        return np.array(pixels, copy=True), 16  # copy: the view would outlive the QImage's buffer
    image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    raw = np.frombuffer(image.constBits(), dtype=np.uint8)
    # Copy: the view is of the QImage's own buffer, which is freed when ``image`` goes out of scope.
    return np.array(raw.reshape(height, image.bytesPerLine() // 4, 4)[:, :width], copy=True), 8


def _read_qt_image(path: Path) -> Frame:
    reader = QtGui.QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise MediaError(f'{path.name}: {reader.errorString()}')
    pixels, depth = _qimage_to_pixels(image)
    return Frame(pixels, linear=False, info={'channels': 'RGBA' if image.hasAlphaChannel() else 'RGB',
                                             'bit_depth': depth})


def _read_exr(path: Path) -> Frame:
    try:
        import OpenEXR
    except ImportError as err:
        raise MediaError('Reading EXR needs the OpenEXR package: pip install -e ".[media]"') from err
    try:
        with OpenEXR.File(str(path)) as exr:
            channels = exr.channels()
            for name in ('RGBA', 'RGB'):
                if name in channels:
                    data = np.asarray(channels[name].pixels, dtype=np.float32)
                    shown = name
                    break
            else:
                if not channels:
                    raise MediaError(f'{path.name}: no image channels')
                shown = sorted(channels)[0]
                data = np.asarray(channels[shown].pixels, dtype=np.float32)
    except MediaError:
        raise
    except Exception as err:  # noqa: BLE001 - OpenEXR raises plain Exception/OSError for bad files
        raise MediaError(f'{path.name}: {err}') from err
    if data.ndim == 2:
        data = np.stack([data, data, data], axis=-1)
    if data.shape[-1] == 3:
        data = np.concatenate([data, np.ones(data.shape[:2] + (1,), dtype=np.float32)], axis=-1)
    return Frame(np.ascontiguousarray(data[..., :4]), linear=True,
                 info={'channels': shown, 'bit_depth': 32})


def read_image(path) -> Frame:
    """Decode one image file.

    Raises:
        MediaError: If the format is not supported or the file cannot be read.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in EXR_EXTENSIONS:
        return _read_exr(path)
    if suffix in QT_IMAGE_EXTENSIONS:
        return _read_qt_image(path)
    raise MediaError(f'{path.name}: unsupported image format {suffix or "(none)"}')


# ---------------------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------------------

_SEQUENCE_NAME = re.compile(r'^(?P<prefix>.*?)(?P<frame>\d+)(?P<suffix>\.[^.]+)$')
_HASH_PATTERN = re.compile(r'(#+)|%0?(\d*)d')


@dataclass
class SequenceInfo:
    """A numbered run of image files in one folder.

    ``padding`` is the digit count of zero-padded frames, or 0 when frames are not padded.
    """
    directory: Path
    prefix: str
    suffix: str
    padding: int
    frames: list[int]

    @property
    def first(self) -> int:
        return self.frames[0]

    @property
    def last(self) -> int:
        return self.frames[-1]

    @property
    def missing(self) -> list[int]:
        """Frame numbers between first and last that have no file."""
        have = set(self.frames)
        return [n for n in range(self.first, self.last + 1) if n not in have]

    @property
    def pattern(self) -> str:
        """The sequence name with ``#`` for each padded digit, e.g. ``shot.####.exr``."""
        return f'{self.prefix}{"#" * (self.padding or 1)}{self.suffix}'

    def path_for(self, frame: int) -> Path:
        return self.directory / f'{self.prefix}{frame:0{self.padding}d}{self.suffix}'


def find_sequence(path) -> SequenceInfo | None:
    """Find the sequence a file belongs to, from any one file in it.

    Returns None when the name has no frame number, or no other file shares its pattern.
    """
    path = Path(path)
    match = _SEQUENCE_NAME.match(path.name)
    if not match or not path.parent.is_dir():
        return None
    prefix, suffix = match['prefix'], match['suffix']
    pattern = re.compile(rf'^{re.escape(prefix)}(?P<frame>\d+){re.escape(suffix)}$', re.IGNORECASE)
    numbers: dict[int, int] = {}  # frame number -> digit count
    for entry in path.parent.iterdir():
        found = pattern.match(entry.name)
        if found and entry.is_file():
            numbers[int(found['frame'])] = len(found['frame'])
    if len(numbers) < 2:
        return None
    lengths = set(numbers.values())
    padded = len(lengths) == 1 and next(iter(lengths)) > 1 or any(
        digits > len(str(frame)) for frame, digits in numbers.items())
    padding = max(lengths) if padded else 0
    return SequenceInfo(path.parent, prefix, suffix, padding, sorted(numbers))


def sequence_from_pattern(pattern) -> SequenceInfo | None:
    """Find a sequence from a pattern such as ``shot.####.exr`` or ``shot.%04d.exr``."""
    pattern = Path(pattern)
    match = _HASH_PATTERN.search(pattern.name)
    if not match:
        return None
    digits = len(match.group(1)) if match.group(1) else int(match.group(2) or 0)
    prefix, suffix = pattern.name[:match.start()], pattern.name[match.end():]
    regex = re.compile(rf'^{re.escape(prefix)}(?P<frame>\d+){re.escape(suffix)}$', re.IGNORECASE)
    numbers = sorted(int(m['frame']) for m in (regex.match(e.name) for e in pattern.parent.iterdir()) if m) \
        if pattern.parent.is_dir() else []
    if not numbers:
        return None
    return SequenceInfo(pattern.parent, prefix, suffix, digits, numbers)


# ---------------------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------------------

class MediaSource:
    """Something the viewer can show frames of."""

    kind = 'media'

    def __init__(self, name: str, first_frame: int = 1, last_frame: int = 1, fps: float = DEFAULT_FPS):
        self.name = name
        self.first_frame = first_frame
        self.last_frame = last_frame
        self.fps = fps

    @property
    def frame_count(self) -> int:
        return self.last_frame - self.first_frame + 1

    def read_frame(self, frame: int) -> Frame:
        """Decode a frame. ``frame`` is clamped to the source's range."""
        raise NotImplementedError

    def close(self) -> None:
        """Release anything held open."""


class ImageSource(MediaSource):
    """A single still image."""

    kind = 'image'

    def __init__(self, path):
        self.path = Path(path)
        super().__init__(self.path.name)
        self._frame = read_image(self.path)

    def read_frame(self, frame: int = 1) -> Frame:
        return self._frame


class SequenceSource(MediaSource):
    """A numbered sequence of images. Missing frames hold the previous frame."""

    kind = 'sequence'

    def __init__(self, sequence: SequenceInfo, fps: float = DEFAULT_FPS):
        self.sequence = sequence
        super().__init__(sequence.pattern, sequence.first, sequence.last, fps)
        self._have = set(sequence.frames)
        self._cache: dict[int, Frame] = {}

    def _nearest_at_or_before(self, frame: int) -> int:
        while frame > self.first_frame and frame not in self._have:
            frame -= 1
        return frame

    def read_frame(self, frame: int) -> Frame:
        frame = self._nearest_at_or_before(min(max(frame, self.first_frame), self.last_frame))
        cached = self._cache.get(frame)
        if cached is None:
            cached = read_image(self.sequence.path_for(frame))
            if len(self._cache) >= 8:  # keep a few for stepping back and forth
                self._cache.pop(next(iter(self._cache)))
            self._cache[frame] = cached
        return cached


class VideoSource(MediaSource):
    """A video file, decoded with ``QtMultimedia``.

    Frames are numbered from 1. ``read_frame`` seeks and returns the frame shown there;
    ``play`` streams frames to a callback at the video's own rate.
    """

    kind = 'video'
    _TIMEOUT_MS = 5000

    def __init__(self, path):
        try:
            from PySide6 import QtMultimedia
        except ImportError as err:
            raise MediaError('Video needs PySide6 QtMultimedia') from err
        self.path = Path(path)
        super().__init__(self.path.name)
        self._mm = QtMultimedia
        self._player = QtMultimedia.QMediaPlayer()
        self._sink = QtMultimedia.QVideoSink()
        self._player.setVideoSink(self._sink)
        self._stream_callback = None
        self._latest: QtGui.QImage | None = None
        self._sink.videoFrameChanged.connect(self._on_video_frame)
        self._player.setSource(QtCore.QUrl.fromLocalFile(str(self.path)))
        self._wait_until(lambda: self._player.mediaStatus() in (
            QtMultimedia.QMediaPlayer.MediaStatus.LoadedMedia, QtMultimedia.QMediaPlayer.MediaStatus.BufferedMedia,
            QtMultimedia.QMediaPlayer.MediaStatus.InvalidMedia), 'open')
        if self._player.mediaStatus() == QtMultimedia.QMediaPlayer.MediaStatus.InvalidMedia:
            raise MediaError(f'{self.path.name}: {self._player.errorString() or "cannot decode this video"}')
        rate = self._player.metaData().value(QtMultimedia.QMediaMetaData.Key.VideoFrameRate)
        self.fps = float(rate) if rate else DEFAULT_FPS
        self.last_frame = max(1, int(round(self._player.duration() / 1000.0 * self.fps)))

    def _wait_until(self, done, what: str) -> None:
        """Run the event loop until ``done()`` is true, or raise on timeout."""
        loop = QtCore.QEventLoop()
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        poll = QtCore.QTimer()
        poll.timeout.connect(lambda: loop.quit() if done() else None)
        timer.start(self._TIMEOUT_MS)
        poll.start(10)
        loop.exec()
        timer.stop()
        poll.stop()
        if not done():
            raise MediaError(f'{self.path.name}: timed out waiting to {what}')

    def _on_video_frame(self, video_frame) -> None:
        if not video_frame.isValid():
            return
        image = video_frame.toImage()
        if image.isNull():
            return
        self._latest = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        if self._stream_callback is not None:
            position_ms = self._player.position()
            self._stream_callback(self._latest, self._frame_at(position_ms))

    def _frame_at(self, position_ms: int) -> int:
        return min(self.last_frame, max(self.first_frame, int(position_ms / 1000.0 * self.fps) + 1))

    @staticmethod
    def _image_to_frame(image: QtGui.QImage) -> Frame:
        pixels, _ = _qimage_to_pixels(image)
        return Frame(pixels, linear=False, info={'channels': 'RGB', 'bit_depth': 8})

    def read_frame(self, frame: int) -> Frame:
        frame = min(max(frame, self.first_frame), self.last_frame)
        self._stream_callback = None
        self._latest = None
        self._player.pause()
        self._player.setPosition(int((frame - 1) / self.fps * 1000.0 + 0.5))
        self._wait_until(lambda: self._latest is not None, f'show frame {frame}')
        return self._image_to_frame(self._latest)

    def play(self, callback) -> None:
        """Stream frames: ``callback(image, frame_number)`` is called as each frame is decoded."""
        self._stream_callback = callback
        self._player.play()

    def pause(self) -> None:
        self._stream_callback = None
        self._player.pause()

    def position_frame(self) -> int:
        """The frame the player is at."""
        return self._frame_at(self._player.position())

    def close(self) -> None:
        self._stream_callback = None
        self._player.stop()
        self._player.setVideoSink(None)


def open_media(path) -> MediaSource:
    """Open an image, image sequence or video as a source.

    An image whose name has a frame number and has siblings opens as a sequence. A
    pattern (``shot.####.exr``, ``shot.%04d.exr``) opens that sequence.

    Raises:
        MediaError: If the file is missing, unsupported or cannot be read.
    """
    path = Path(path)
    sequence = sequence_from_pattern(path) if not path.exists() else None
    if sequence is not None:
        return SequenceSource(sequence)
    if not path.is_file():
        raise MediaError(f'{path}: no such file')
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return VideoSource(path)
    if suffix in IMAGE_EXTENSIONS:
        sequence = find_sequence(path)
        if sequence is not None:
            return SequenceSource(sequence)
        return ImageSource(path)
    raise MediaError(f'{path.name}: unsupported file type {suffix or "(none)"}')
