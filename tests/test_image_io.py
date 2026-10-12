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
"""Tests for deda.core._image_io (Qt decode paths, plus HEIC/RAW with stand-in libraries)."""
import sys
import types

import numpy as np
import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from deda.core import _image_io


@pytest.fixture(scope='module', autouse=True)
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def png(tmp_path):
    path = tmp_path / 'wide.png'
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor(200, 10, 10))
    assert image.save(str(path))
    return path


def jpeg_bytes(width=8, height=4):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor(10, 200, 10))
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, 'JPG')
    return bytes(buf.data())


class TestBasics:
    def test_is_image_file(self):
        assert _image_io.is_image_file('a/b/photo.JPG')
        assert _image_io.is_image_file('x.cr2') and _image_io.is_image_file('x.heic')
        assert not _image_io.is_image_file('movie.mp4')

    def test_is_available_reports_missing_extras(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'pillow_heif', None)
        ok, message = _image_io.is_available()
        assert not ok and 'raw_formats' in message

    def test_is_available_when_both_libraries_import(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'pillow_heif', types.ModuleType('pillow_heif'))
        monkeypatch.setitem(sys.modules, 'rawpy', types.ModuleType('rawpy'))
        assert _image_io.is_available() == (True, '')


class TestStandardFormats:
    def test_size_full_and_preview(self, png):
        assert _image_io.read_image_size(png) == (40, 20)
        full = _image_io.load_full_qimage(png)
        assert (full.width(), full.height()) == (40, 20)
        preview = _image_io.load_preview_qimage(png, max_size=10)
        assert max(preview.width(), preview.height()) == 10
        assert preview.width() > preview.height()

    def test_unreadable_file_gives_none_and_a_null_image(self, tmp_path):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'not an image')
        assert _image_io.read_image_size(bad) is None
        assert _image_io.load_full_qimage(bad).isNull()

    def test_rotated_orientation_swaps_the_reported_size(self, png, monkeypatch):
        monkeypatch.setattr(_image_io, '_swaps_dimensions', lambda reader: True)
        assert _image_io.read_image_size(png) == (20, 40)
        preview = _image_io.load_preview_qimage(png, max_size=10)
        assert preview.isNull() or preview.width() <= 20

    def test_swaps_dimensions_reads_the_reader_transformation(self):
        class Reader:
            def __init__(self, flag):
                self._flag = flag

            def transformation(self):
                return self._flag

        rotate = QtGui.QImageIOHandler.Transformation.TransformationRotate90
        none = QtGui.QImageIOHandler.Transformation.TransformationNone
        assert _image_io._swaps_dimensions(Reader(rotate))
        assert not _image_io._swaps_dimensions(Reader(none))


class TestOptionalLibrariesMissing:
    @pytest.mark.parametrize('name', ['photo.heic', 'photo.cr2'])
    def test_everything_degrades_when_the_libraries_are_not_installed(self, tmp_path, monkeypatch, name):
        for mod in ('pillow_heif', 'rawpy'):
            monkeypatch.setitem(sys.modules, mod, None)
        path = tmp_path / name
        path.write_bytes(b'x')
        assert _image_io.read_image_size(path) is None
        assert _image_io.load_full_qimage(path).isNull()
        assert _image_io.load_preview_qimage(path).isNull()

    @pytest.mark.parametrize('name', ['photo.heic', 'photo.cr2'])
    def test_other_decode_errors_are_swallowed(self, tmp_path, monkeypatch, name):
        def boom(*args, **kwargs):
            raise OSError('corrupt')

        for fn in ('_heic_size', '_heic_full', '_heic_preview', '_raw_size', '_raw_full', '_raw_preview'):
            monkeypatch.setattr(_image_io, fn, boom)
        path = tmp_path / name
        assert _image_io.read_image_size(path) is None
        assert _image_io.load_full_qimage(path).isNull()
        assert _image_io.load_preview_qimage(path).isNull()


@pytest.fixture
def fake_heif(monkeypatch, png):
    heif = types.ModuleType('pillow_heif')
    heif.registered = 0

    def register_heif_opener():
        heif.registered += 1

    class HeifFile:
        size = (64, 48)

    heif.register_heif_opener = register_heif_opener
    heif.open_heif = lambda path, convert_hdr_to_8bit=False: HeifFile()
    monkeypatch.setitem(sys.modules, 'pillow_heif', heif)
    monkeypatch.setattr(_image_io, '_heif_opener_registered', False)
    return heif


class TestHeic:
    def test_size_registers_the_opener_once(self, fake_heif, tmp_path):
        path = tmp_path / 'a.heic'
        assert _image_io.read_image_size(path) == (64, 48)
        assert _image_io.read_image_size(path) == (64, 48)
        assert fake_heif.registered == 1

    def test_size_none_when_the_file_cannot_be_opened(self, fake_heif, tmp_path):
        fake_heif.open_heif = lambda *a, **k: None
        assert _image_io.read_image_size(tmp_path / 'a.heic') is None

    def test_full_and_preview_decode_through_pillow(self, fake_heif, png, tmp_path):
        heic = tmp_path / 'photo.heic'
        heic.write_bytes(png.read_bytes())    # Pillow identifies the data by content
        full = _image_io.load_full_qimage(heic)
        assert (full.width(), full.height()) == (40, 20)
        small = _image_io.load_preview_qimage(heic, max_size=10)
        assert max(small.width(), small.height()) == 10


@pytest.fixture
def fake_rawpy(monkeypatch):
    raw = types.ModuleType('rawpy')

    class NoThumb(Exception):
        pass

    class Unsupported(Exception):
        pass

    class ThumbFormat:
        JPEG = 'jpeg'
        BITMAP = 'bitmap'

    class Thumb:
        format = ThumbFormat.JPEG
        data = jpeg_bytes()

    state = types.SimpleNamespace(thumb=Thumb, thumb_error=None)

    class Raw:
        sizes = types.SimpleNamespace(width=6000, height=4000)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def postprocess(self, **kwargs):
            return np.full((20, 40, 3), 77, dtype=np.uint8)

        def extract_thumb(self):
            if state.thumb_error:
                raise state.thumb_error()
            return state.thumb

    raw.LibRawNoThumbnailError = NoThumb
    raw.LibRawUnsupportedThumbnailError = Unsupported
    raw.ThumbFormat = ThumbFormat
    raw.imread = lambda path: Raw()
    raw.state = state
    monkeypatch.setitem(sys.modules, 'rawpy', raw)
    return raw


class TestRaw:
    def test_size(self, fake_rawpy, tmp_path):
        assert _image_io.read_image_size(tmp_path / 'a.nef') == (6000, 4000)

    def test_full_demosaic(self, fake_rawpy, tmp_path):
        image = _image_io.load_full_qimage(tmp_path / 'a.dng')
        assert (image.width(), image.height()) == (40, 20)
        assert QtGui.QColor(image.pixel(1, 1)).red() == 77

    def test_preview_uses_the_embedded_jpeg(self, fake_rawpy, tmp_path):
        image = _image_io.load_preview_qimage(tmp_path / 'a.arw', max_size=4)
        assert max(image.width(), image.height()) == 4

    @pytest.mark.parametrize('error_name', ['LibRawNoThumbnailError', 'LibRawUnsupportedThumbnailError'])
    def test_preview_falls_back_to_a_demosaic_without_a_thumbnail(self, fake_rawpy, tmp_path, error_name):
        fake_rawpy.state.thumb_error = getattr(fake_rawpy, error_name)
        image = _image_io.load_preview_qimage(tmp_path / 'a.arw', max_size=10)
        assert max(image.width(), image.height()) == 10

    def test_preview_falls_back_when_the_thumbnail_is_not_a_jpeg(self, fake_rawpy, tmp_path):
        fake_rawpy.state.thumb = types.SimpleNamespace(format=fake_rawpy.ThumbFormat.BITMAP, data=b'')
        image = _image_io.load_preview_qimage(tmp_path / 'a.arw', max_size=10)
        assert max(image.width(), image.height()) == 10

    def test_preview_falls_back_when_the_jpeg_is_corrupt(self, fake_rawpy, tmp_path):
        fake_rawpy.state.thumb = types.SimpleNamespace(format=fake_rawpy.ThumbFormat.JPEG, data=b'junk')
        image = _image_io.load_preview_qimage(tmp_path / 'a.arw', max_size=10)
        assert max(image.width(), image.height()) == 10

    def test_preview_fallback_with_a_null_demosaic_returns_null(self, fake_rawpy, tmp_path, monkeypatch):
        fake_rawpy.state.thumb_error = fake_rawpy.LibRawNoThumbnailError
        monkeypatch.setattr(_image_io, '_raw_full', lambda path: QtGui.QImage())
        assert _image_io.load_preview_qimage(tmp_path / 'a.arw').isNull()
