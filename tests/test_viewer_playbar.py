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
"""Tests for the viewer playbar and its timeline widget."""
import pytest
from PySide6 import QtCore, QtTest

from deda.core.viewer._playbar import Playbar, _TimelineWidget


@pytest.fixture
def timeline(qapp):
    widget = _TimelineWidget()
    widget.resize(404, 32)
    widget.setFrameRange(0, 100)
    widget.show()
    yield widget
    widget.close()


def click_at(widget, frame):
    x = widget._frameToX(frame)
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(x, 16))


class TestTimeline:
    def test_range_is_clamped_to_at_least_one_frame(self, timeline):
        timeline.setFrameRange(10, 3)
        assert timeline.frameRange() == (10, 11)

    def test_set_frame_clamps_and_emits_only_on_change(self, timeline):
        seen = []
        timeline.frameChanged.connect(seen.append)
        timeline.setFrame(500)
        timeline.setFrame(500)
        timeline.setFrame(-5)
        assert seen == [100, 0] and timeline.frame() == 0

    def test_shrinking_the_range_pulls_the_frame_in(self, timeline):
        timeline.setFrame(90)
        timeline.setFrameRange(0, 50)
        assert timeline.frame() == 50

    def test_frame_x_mapping_round_trips(self, timeline):
        for frame in (0, 25, 50, 100):
            assert abs(timeline._xToFrame(timeline._frameToX(frame)) - frame) <= 1

    def test_x_outside_the_track_is_clamped(self, timeline):
        assert timeline._xToFrame(-100) == 0 and timeline._xToFrame(10000) == 100

    def test_degenerate_geometry(self, timeline):
        timeline.resize(4, 32)
        assert timeline._xToFrame(0) == timeline._frame_min
        timeline._frame_max = timeline._frame_min
        assert timeline._frameToX(5) == timeline._trackRect().left()

    def test_clicking_the_track_jumps_the_playhead(self, timeline):
        click_at(timeline, 75)
        assert abs(timeline.frame() - 75) <= 1

    def test_dragging_the_playhead(self, timeline):
        timeline.setFrame(10)
        start = timeline._playheadRect().center()
        QtTest.QTest.mousePress(timeline, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, start)
        assert timeline._dragging
        target = QtCore.QPoint(timeline._frameToX(60), start.y())
        move = QtTest.QTest.mouseMove
        move(timeline, target)
        assert abs(timeline.frame() - 60) <= 1
        QtTest.QTest.mouseRelease(timeline, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, target)
        assert not timeline._dragging

    def test_moves_and_releases_without_a_drag_do_nothing(self, timeline):
        before = timeline.frame()
        QtTest.QTest.mouseMove(timeline, QtCore.QPoint(200, 16))
        QtTest.QTest.mouseRelease(timeline, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(200, 16))
        assert timeline.frame() == before

    def test_right_click_is_ignored(self, timeline):
        QtTest.QTest.mouseClick(timeline, QtCore.Qt.RightButton, QtCore.Qt.NoModifier, QtCore.QPoint(300, 16))
        assert timeline.frame() == 0

    def test_click_outside_the_track_is_ignored(self, timeline):
        QtTest.QTest.mouseClick(timeline, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(1, 1))
        assert timeline.frame() == 0

    def test_it_paints_ticks_and_playhead(self, timeline):
        timeline.setFrame(40)
        image = timeline.grab().toImage()
        assert not image.isNull() and image.width() == 404

    def test_painting_a_tiny_widget_does_not_fail(self, timeline):
        timeline.resize(6, 6)
        assert not timeline.grab().isNull()


class TestPlaybar:
    @pytest.fixture
    def bar(self, qapp):
        bar = Playbar()
        bar.resize(500, 40)
        yield bar
        bar.close()

    def test_frame_range_and_label(self, bar):
        bar.setFrameRange(1001, 1100)
        assert bar.frameRange() == (1001, 1100) and bar._frame_label.text() == '1001'
        bar.setFrame(1050)
        assert bar.frame() == 1050 and bar._frame_label.text() == '1050'

    def test_frame_changes_and_buttons_emit_signals(self, bar):
        frames, plays, stops = [], [], []
        bar.frameChanged.connect(frames.append)
        bar.playClicked.connect(lambda: plays.append(1))
        bar.stopClicked.connect(lambda: stops.append(1))
        bar.setFrameRange(0, 10)
        bar.setFrame(4)
        bar._play_btn.click()
        bar._stop_btn.click()
        assert frames[-1] == 4 and plays == [1] and stops == [1]
