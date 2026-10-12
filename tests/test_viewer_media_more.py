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
"""More tests for 2D media decoding, the video source (against a stand-in player) and the media widget."""
import sys
import types

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtTest

from deda.core.viewer import _media, _media_view


@pytest.fixture
def png_dir(tmp_path):
    for frame in (1, 2, 3, 5):
        image = QtGui.QImage(10, 6, QtGui.QImage.Format.Format_RGBA8888)
        image.fill(QtGui.QColor(frame * 40, 10, 10, 255))
        image.save(str(tmp_path / f'shot.{frame:04d}.png'))
    return tmp_path


class TestDecoding:
    def test_sixteen_bit_images_become_float(self, qapp):
        image = QtGui.QImage(4, 3, QtGui.QImage.Format.Format_RGBA64)
        image.fill(QtGui.QColor(255, 0, 0))
        pixels, depth = _media._qimage_to_pixels(image)
        assert depth == 16 and pixels.dtype == np.float32 and pixels.shape == (3, 4, 4)
        assert pixels[0, 0, 0] == pytest.approx(1.0) and pixels[0, 0, 1] == pytest.approx(0.0)

    def test_eight_bit_images_have_no_row_padding(self, qapp):
        image = QtGui.QImage(5, 2, QtGui.QImage.Format.Format_RGB888)
        image.fill(QtGui.QColor(0, 255, 0))
        pixels, depth = _media._qimage_to_pixels(image)
        assert depth == 8 and pixels.shape == (2, 5, 4) and tuple(pixels[1, 4]) == (0, 255, 0, 255)

    def test_reading_an_unreadable_image_names_the_file(self, tmp_path, qapp):
        bad = tmp_path / 'oops.png'
        bad.write_bytes(b'nope')
        with pytest.raises(_media.MediaError, match='oops.png'):
            _media.read_image(bad)


class TestExr:
    @pytest.fixture
    def openexr(self):
        return pytest.importorskip('OpenEXR')

    def write(self, openexr, path, channels):
        with openexr.File({'compression': openexr.ZIP_COMPRESSION, 'type': openexr.scanlineimage}, channels) as exr:
            exr.write(str(path))

    def test_rgb_gets_an_opaque_alpha(self, openexr, tmp_path):
        path = tmp_path / 'rgb.exr'
        self.write(openexr, path, {'RGB': np.full((4, 6, 3), 0.5, dtype=np.float32)})
        frame = _media.read_image(path)
        assert frame.pixels.shape == (4, 6, 4) and frame.linear and frame.pixels[0, 0, 3] == 1.0
        assert frame.info['channels'] == 'RGB'

    def test_a_single_named_channel_is_shown_as_grey(self, openexr, tmp_path):
        path = tmp_path / 'depth.exr'
        self.write(openexr, path, {'Z': np.full((4, 6), 2.0, dtype=np.float32)})
        frame = _media.read_image(path)
        assert frame.info['channels'] == 'Z' and tuple(frame.pixels[0, 0]) == (2.0, 2.0, 2.0, 1.0)

    def test_a_corrupt_exr_is_a_media_error(self, openexr, tmp_path):
        path = tmp_path / 'bad.exr'
        path.write_bytes(b'not an exr')
        with pytest.raises(_media.MediaError, match='bad.exr'):
            _media.read_image(path)

    def test_a_file_without_channels(self, tmp_path, monkeypatch):
        fake = types.ModuleType('OpenEXR')

        class File:
            def __init__(self, path):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def channels(self):
                return {}

        fake.File = File
        monkeypatch.setitem(sys.modules, 'OpenEXR', fake)
        with pytest.raises(_media.MediaError, match='no image channels'):
            _media._read_exr(tmp_path / 'empty.exr')


class TestSequenceSource:
    def test_cache_is_bounded_and_reused(self, png_dir, qapp):
        source = _media.open_media(png_dir / 'shot.0001.png')
        assert source.kind == 'sequence' and (source.first_frame, source.last_frame) == (1, 5)
        first = source.read_frame(1)
        assert source.read_frame(1) is first
        for frame in (2, 3, 5):
            source.read_frame(frame)
        assert len(source._cache) <= 8

    def test_eviction_when_the_cache_is_full(self, png_dir, qapp):
        source = _media.open_media(png_dir / 'shot.0001.png')
        source._cache.update({100 + i: object() for i in range(8)})
        source.read_frame(2)
        assert len(source._cache) == 8 and 2 in source._cache

    def test_frames_beyond_the_range_are_clamped(self, png_dir, qapp):
        source = _media.open_media(png_dir / 'shot.0001.png')
        assert source.read_frame(99) is source.read_frame(5)
        assert source.read_frame(-4) is source.read_frame(1)


class FakePlayer:
    """Stands in for QMediaPlayer: positions are recorded, frames are delivered by the test."""

    def __init__(self):
        self.events = []
        self._position = 0

    def pause(self):
        self.events.append('pause')

    def play(self):
        self.events.append('play')

    def stop(self):
        self.events.append('stop')

    def setVideoSink(self, sink):
        self.events.append(('sink', sink))

    def setPosition(self, ms):
        self._position = ms
        self.events.append(('seek', ms))

    def position(self):
        return self._position


@pytest.fixture
def video(qapp):
    """A VideoSource built without opening any file: 10 frames at 25 fps."""
    source = _media.VideoSource.__new__(_media.VideoSource)
    _media.MediaSource.__init__(source, 'clip.mp4')
    source.path = _media.Path('clip.mp4')
    source.fps = 25.0
    source.last_frame = 10
    source._player = FakePlayer()
    source._stream_callback = None
    source._latest = None
    return source


def solid_frame(color=(10, 200, 30)):
    image = QtGui.QImage(6, 4, QtGui.QImage.Format.Format_RGBA8888)
    image.fill(QtGui.QColor(*color))
    return image


class FakeVideoFrame:
    def __init__(self, image=None, valid=True):
        self._image = image
        self._valid = valid

    def isValid(self):
        return self._valid

    def toImage(self):
        return self._image if self._image is not None else QtGui.QImage()


class TestVideoSource:
    def test_frame_numbers_follow_the_position(self, video):
        assert video._frame_at(0) == 1 and video._frame_at(400) == 11 - 1 and video._frame_at(10 ** 6) == 10
        video._player._position = 80
        assert video.position_frame() == 3

    def test_streaming_frames_reach_the_callback(self, video):
        got = []
        video._stream_callback = lambda image, frame: got.append(frame)
        video._player._position = 120
        video._on_video_frame(FakeVideoFrame(solid_frame()))
        assert got == [4] and video._latest is not None

    def test_invalid_or_empty_frames_are_ignored(self, video):
        video._on_video_frame(FakeVideoFrame(valid=False))
        video._on_video_frame(FakeVideoFrame(image=None))
        assert video._latest is None

    def test_read_frame_seeks_and_waits_for_the_decoded_frame(self, video):
        video._wait_until = lambda done, what: setattr(video, '_latest', solid_frame()) or None
        frame = video.read_frame(6)
        assert ('seek', 200) in video._player.events and 'pause' in video._player.events
        assert tuple(frame.pixels[0, 0]) == (10, 200, 30, 255) and not frame.linear

    def test_read_frame_clamps_and_cancels_streaming(self, video):
        video._stream_callback = lambda *a: None
        video._wait_until = lambda done, what: setattr(video, '_latest', solid_frame())
        video.read_frame(500)
        assert ('seek', 360) in video._player.events and video._stream_callback is None

    def test_play_pause_close(self, video):
        callback = lambda image, frame: None
        video.play(callback)
        assert video._stream_callback is callback and 'play' in video._player.events
        video.pause()
        assert video._stream_callback is None and video._player.events[-1] == 'pause'
        video.close()
        assert 'stop' in video._player.events and video._player.events[-1] == ('sink', None)

    def test_wait_until_returns_when_done_and_times_out_otherwise(self, video, qapp):
        video._TIMEOUT_MS = 50
        video._wait_until(lambda: True, 'start')
        with pytest.raises(_media.MediaError, match='timed out waiting to never'):
            video._wait_until(lambda: False, 'never')

    def test_opening_a_missing_video_through_open_media(self, tmp_path):
        with pytest.raises(_media.MediaError, match='no such file'):
            _media.open_media(tmp_path / 'absent.mp4')

    def test_missing_multimedia_is_reported(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'PySide6.QtMultimedia', None)
        with pytest.raises(_media.MediaError, match='QtMultimedia'):
            _media.VideoSource('whatever.mp4')


@pytest.fixture
def view(qapp, png_dir):
    widget = _media_view.MediaViewWidget()
    widget.resize(200, 120)
    widget.show()
    widget.set_source(_media.open_media(png_dir / 'shot.0001.png'))
    yield widget
    widget.set_source(None)
    widget.close()


class TestMediaView:
    def test_empty_widget_paints_a_hint(self, qapp):
        widget = _media_view.MediaViewWidget()
        widget.resize(200, 100)
        assert not widget.grab().isNull() and widget.hud_lines() == []
        assert widget.set_frame(3) is False and widget.pixel_at(0, 0) is None
        widget.set_source(None)

    def test_painting_with_and_without_the_hud(self, view):
        with_hud = view.grab().toImage()
        view.set_show_hud(False)
        without = view.grab().toImage()
        assert view.show_hud is False and with_hud != without

    def test_alpha_images_get_a_checkerboard(self, view, tmp_path):
        image = QtGui.QImage(8, 8, QtGui.QImage.Format.Format_ARGB32)
        image.fill(QtGui.QColor(255, 0, 0, 100))
        image.save(str(tmp_path / 'alpha.png'))
        view.set_source(_media.open_media(tmp_path / 'alpha.png'))
        assert not view.grab().isNull()

    def test_wheel_zoom_keeps_the_point_under_the_cursor(self, view):
        view.actual_size()
        before = view.zoom
        point = QtCore.QPointF(100, 60)
        event = QtGui.QWheelEvent(point, view.mapToGlobal(point), QtCore.QPoint(), QtCore.QPoint(0, 120),
                                  QtCore.Qt.NoButton, QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
        view.wheelEvent(event)
        assert view.zoom == pytest.approx(before * 1.25)
        zero = QtGui.QWheelEvent(point, view.mapToGlobal(point), QtCore.QPoint(), QtCore.QPoint(0, 0),
                                 QtCore.Qt.NoButton, QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
        view.wheelEvent(zero)
        assert view.zoom == pytest.approx(before * 1.25)

    def test_wheel_without_an_image_does_nothing(self, qapp):
        widget = _media_view.MediaViewWidget()
        point = QtCore.QPointF(5, 5)
        event = QtGui.QWheelEvent(point, point, QtCore.QPoint(), QtCore.QPoint(0, 120),
                                  QtCore.Qt.NoButton, QtCore.Qt.NoModifier, QtCore.Qt.NoScrollPhase, False)
        widget.wheelEvent(event)
        assert widget.zoom == 1.0

    def test_dragging_pans_and_double_click_refits(self, view):
        view.actual_size()
        start = QtCore.QPoint(50, 50)
        QtTest.QTest.mousePress(view, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
        before = QtCore.QPointF(view._offset)
        QtTest.QTest.mouseMove(view, QtCore.QPoint(70, 65))
        assert view._offset != before or view._drag_start is not None
        QtTest.QTest.mouseRelease(view, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(70, 65))
        assert view._drag_start is None
        QtTest.QTest.mouseDClick(view, QtCore.Qt.LeftButton)
        assert view._fit_on_resize

    def test_right_button_does_not_start_a_drag(self, view):
        QtTest.QTest.mousePress(view, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(10, 10))
        assert view._drag_start is None

    def test_cursor_values_show_in_the_hud_and_clear_on_leave(self, view):
        view.actual_size()
        centre = view._offset + QtCore.QPointF(2.5, 2.5)
        QtTest.QTest.mouseMove(view, centre.toPoint())
        assert any(line.startswith('(') for line in view.hud_lines())
        view.leaveEvent(None)
        assert not any(line.startswith('(') for line in view.hud_lines())

    def test_hud_reports_sequence_state(self, view):
        view.set_exposure(1.5)
        view.set_channel('g')
        lines = '\n'.join(view.hud_lines())
        assert 'missing frame' in lines and 'exposure +1.5' in lines and 'channel: g' in lines
        assert 'frame 1' in lines and 'shot' in lines

    def test_bad_channel_is_rejected(self, view):
        with pytest.raises(ValueError):
            view.set_channel('xyz')

    def test_pixel_lookup(self, view):
        assert view.pixel_at(0, 0)[0] == 40 and view.pixel_at(-1, 0) is None and view.pixel_at(10, 0) is None

    def test_show_decoded_displays_a_streamed_frame(self, view):
        view.show_decoded(solid_frame((1, 2, 3)), 7)
        assert view.frame_number == 7 and view.pixel_at(0, 0)[:3] == (1, 2, 3)

    def test_changing_the_source_closes_the_previous_one(self, view, png_dir):
        closed = []
        first = view.source
        first.close = lambda: closed.append(True)
        view.set_source(_media.open_media(png_dir / 'shot.0002.png'))
        assert closed == [True]
        view.set_source(view.source)               # the same source again is not closed
        assert closed == [True]

    def test_resize_refits_until_the_user_zooms(self, view):
        view.resize(300, 200)
        fitted = view.zoom
        view.actual_size()
        view.resize(100, 80)
        assert view.zoom == 1.0 and fitted != 1.0

    def test_failed_frames_emit_an_error(self, view, monkeypatch):
        errors = []
        view.errorOccurred.connect(errors.append)

        def broken(frame):
            raise _media.MediaError('bad frame')

        monkeypatch.setattr(view.source, 'read_frame', broken)
        assert view.set_frame(2) is False and errors == ['bad frame']
