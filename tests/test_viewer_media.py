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
"""Tests for the viewer's 2D media: sequences, decoding, display and the viewport widget."""
import os

import numpy as np
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6 import QtGui, QtWidgets  # noqa: E402

from deda.core.viewer import _media, _media_view  # noqa: E402


@pytest.fixture(scope='module')
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def save_png(path, color, size=(8, 6)):
    image = QtGui.QImage(size[0], size[1], QtGui.QImage.Format.Format_RGBA8888)
    image.fill(QtGui.QColor(*color))
    assert image.save(str(path))
    return path


@pytest.fixture
def png_sequence(tmp_path, qapp):
    """shot.0001.png ... shot.0004.png, each a different red level."""
    for frame in range(1, 5):
        save_png(tmp_path / f'shot.{frame:04d}.png', (frame * 50, 0, 0, 255))
    return tmp_path


# -- sequence detection --------------------------------------------------------------------

def test_find_sequence_from_any_frame(png_sequence):
    for name in ('shot.0001.png', 'shot.0003.png'):
        sequence = _media.find_sequence(png_sequence / name)
        assert sequence.frames == [1, 2, 3, 4]
        assert sequence.padding == 4
        assert (sequence.first, sequence.last) == (1, 4)
        assert sequence.pattern == 'shot.####.png'
        assert sequence.path_for(2).name == 'shot.0002.png'


@pytest.mark.parametrize('names, pattern', [
    (['a_001.png', 'a_002.png'], 'a_###.png'),
    (['a1.png', 'a2.png', 'a10.png'], 'a#.png'),       # unpadded, so frame numbers differ in length
    (['v2_shot.1001.exr', 'v2_shot.1002.exr'], 'v2_shot.####.exr'),
])
def test_sequence_naming_styles(tmp_path, names, pattern):
    for name in names:
        (tmp_path / name).write_bytes(b'')
    sequence = _media.find_sequence(tmp_path / names[0])
    assert sequence.pattern == pattern
    assert [sequence.path_for(f).name for f in sequence.frames] == names


def test_missing_frames_are_reported(tmp_path):
    for frame in (1, 2, 5):
        (tmp_path / f'x.{frame:03d}.png').write_bytes(b'')
    sequence = _media.find_sequence(tmp_path / 'x.001.png')
    assert sequence.missing == [3, 4]


def test_a_lone_numbered_file_is_not_a_sequence(tmp_path):
    (tmp_path / 'only.0001.png').write_bytes(b'')
    (tmp_path / 'other.0001.png').write_bytes(b'')
    assert _media.find_sequence(tmp_path / 'only.0001.png') is None
    assert _media.find_sequence(tmp_path / 'no_number.png') is None


def test_sequence_from_pattern(png_sequence):
    for text in ('shot.####.png', 'shot.%04d.png'):
        sequence = _media.sequence_from_pattern(png_sequence / text)
        assert sequence.frames == [1, 2, 3, 4] and sequence.padding == 4
    assert _media.sequence_from_pattern(png_sequence / 'none.####.png') is None


# -- decoding and display -----------------------------------------------------------------

def test_read_png(tmp_path, qapp):
    frame = _media.read_image(save_png(tmp_path / 'a.png', (10, 20, 30, 255)))
    assert (frame.width, frame.height) == (8, 6)
    assert frame.pixels.dtype == np.uint8 and not frame.linear
    assert tuple(frame.pixels[0, 0]) == (10, 20, 30, 255)


def test_unsupported_and_missing_files(tmp_path):
    (tmp_path / 'x.xyz').write_bytes(b'')
    with pytest.raises(_media.MediaError, match='unsupported'):
        _media.read_image(tmp_path / 'x.xyz')
    with pytest.raises(_media.MediaError):
        _media.open_media(tmp_path / 'nope.png')
    (tmp_path / 'bad.png').write_bytes(b'not a png')
    with pytest.raises(_media.MediaError):
        _media.read_image(tmp_path / 'bad.png')


def test_exr_round_trip(tmp_path):
    OpenEXR = pytest.importorskip('OpenEXR')
    data = np.random.default_rng(0).random((5, 7, 4)).astype(np.float32) * 4.0  # above 1: HDR
    path = tmp_path / 'a.exr'
    with OpenEXR.File({'compression': OpenEXR.ZIP_COMPRESSION, 'type': OpenEXR.scanlineimage},
                      {'RGBA': data}) as exr:
        exr.write(str(path))
    frame = _media.read_image(path)
    assert frame.linear and frame.pixels.dtype == np.float32
    np.testing.assert_allclose(frame.pixels, data)


def test_exr_without_openexr_explains_how_to_install(tmp_path, monkeypatch):
    (tmp_path / 'a.exr').write_bytes(b'')
    monkeypatch.setitem(__import__('sys').modules, 'OpenEXR', None)
    with pytest.raises(_media.MediaError, match='media'):
        _media.read_image(tmp_path / 'a.exr')


def pixel(image, x=0, y=0):
    colour = image.pixelColor(x, y)
    return colour.red(), colour.green(), colour.blue(), colour.alpha()


def test_display_of_an_8_bit_frame_is_unchanged(qapp):
    frame = _media.Frame(np.full((2, 2, 4), (10, 20, 30, 255), dtype=np.uint8))
    assert pixel(_media.frame_to_qimage(frame)) == (10, 20, 30, 255)


def test_channel_isolation(qapp):
    frame = _media.Frame(np.full((2, 2, 4), (200, 100, 50, 128), dtype=np.uint8))
    assert pixel(_media.frame_to_qimage(frame, 'r')) == (200, 200, 200, 255)
    assert pixel(_media.frame_to_qimage(frame, 'b')) == (50, 50, 50, 255)
    assert pixel(_media.frame_to_qimage(frame, 'a')) == (128, 128, 128, 255)
    assert pixel(_media.frame_to_qimage(frame, 'rgb')) == (200, 100, 50, 255)
    with pytest.raises(ValueError):
        _media.frame_to_qimage(frame, 'x')


def test_exposure_scales_8_bit_by_stops(qapp):
    frame = _media.Frame(np.full((1, 1, 4), (50, 50, 50, 255), dtype=np.uint8))
    assert pixel(_media.frame_to_qimage(frame, exposure=1.0))[0] == 100
    assert pixel(_media.frame_to_qimage(frame, exposure=-1.0))[0] == 25


def test_linear_float_gets_the_srgb_curve(qapp):
    frame = _media.Frame(np.full((1, 1, 4), (0.18, 0.18, 0.18, 1.0), dtype=np.float32), linear=True)
    assert abs(pixel(_media.frame_to_qimage(frame))[0] - 118) <= 1     # sRGB(0.18) is about 0.461
    assert pixel(_media.frame_to_qimage(
        _media.Frame(np.full((1, 1, 4), 9.0, dtype=np.float32), linear=True)))[:3] == (255, 255, 255)  # clips


# -- sources -------------------------------------------------------------------------------

def test_open_media_picks_the_right_source(png_sequence, tmp_path, qapp):
    sequence_source = _media.open_media(png_sequence / 'shot.0002.png')
    assert sequence_source.kind == 'sequence'
    assert (sequence_source.first_frame, sequence_source.last_frame, sequence_source.frame_count) == (1, 4, 4)
    single = _media.open_media(save_png(tmp_path / 'single.png', (1, 2, 3, 255)))
    assert single.kind == 'image' and single.frame_count == 1
    assert _media.open_media(png_sequence / 'shot.%04d.png').kind == 'sequence'


def test_sequence_reads_the_requested_frame(png_sequence, qapp):
    source = _media.open_media(png_sequence / 'shot.0001.png')
    assert [int(source.read_frame(f).pixels[0, 0, 0]) for f in (1, 2, 4)] == [50, 100, 200]
    assert int(source.read_frame(99).pixels[0, 0, 0]) == 200   # clamped to the last frame
    assert int(source.read_frame(-5).pixels[0, 0, 0]) == 50    # and the first


def test_a_missing_frame_holds_the_previous_one(tmp_path, qapp):
    for frame in (1, 2, 5, 6):
        save_png(tmp_path / f'g.{frame:03d}.png', (frame * 10, 0, 0, 255))
    source = _media.open_media(tmp_path / 'g.001.png')
    assert int(source.read_frame(4).pixels[0, 0, 0]) == 20    # frames 3 and 4 are missing: hold 2


def test_is_media_file():
    assert _media.is_media_file('a/b/shot.0001.EXR') and _media.is_media_file('x.mp4')
    assert not _media.is_media_file('scene.usda')


# -- the viewport widget --------------------------------------------------------------------

@pytest.fixture
def view(qapp):
    widget = _media_view.MediaViewWidget()
    widget.resize(400, 300)
    yield widget
    widget.set_source(None)


def test_widget_shows_a_frame_and_fits_it(view, png_sequence):
    view.set_source(_media.open_media(png_sequence / 'shot.0001.png'))
    assert view.frame_number == 1
    assert view.zoom == pytest.approx(min(400 / 8, 300 / 6))   # fitted
    assert view.set_frame(3) and view.frame_number == 3
    assert view.pixel_at(0, 0)[0] == 150
    assert view.pixel_at(99, 99) is None


def test_widget_zoom_and_actual_size(view, png_sequence):
    view.set_source(_media.open_media(png_sequence / 'shot.0001.png'))
    view.actual_size()
    assert view.zoom == 1.0
    view.fit()
    assert view.zoom > 1.0


def test_widget_channel_and_exposure(view, png_sequence):
    view.set_source(_media.open_media(png_sequence / 'shot.0004.png'))
    view.set_channel('g')
    assert view.channel == 'g'
    with pytest.raises(ValueError):
        view.set_channel('nope')
    view.set_exposure(2.0)
    assert view.exposure == 2.0


def test_widget_hud_describes_the_media(view, png_sequence):
    assert view.hud_lines() == []
    view.set_source(_media.open_media(png_sequence / 'shot.0002.png'))
    lines = view.hud_lines()
    assert lines[0] == 'shot.####.png'
    assert '8 x 6' in lines[1]
    assert any('frame 1' in line for line in lines)


def test_widget_reports_a_bad_frame_without_raising(view, png_sequence):
    errors = []
    view.errorOccurred.connect(errors.append)
    view.set_source(_media.open_media(png_sequence / 'shot.0001.png'))
    (png_sequence / 'shot.0003.png').write_bytes(b'corrupt')
    assert view.set_frame(3) is False
    assert errors and 'shot.0003.png' in errors[0]
