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
"""Tests for the tiled upscaler, with stand-ins for torch, spandrel and huggingface_hub."""
import sys
import types

import numpy as np
import pytest
from PySide6 import QtCore, QtGui

from deda.plugins.compare import _upscale


class FakeTensor:
    """The few torch.Tensor operations upscale_image uses, backed by numpy."""

    def __init__(self, array):
        self.array = array

    def to(self, target):
        if isinstance(target, np.dtype) or target in (np.float32, np.uint8):
            return FakeTensor(self.array.astype(target))
        return self

    def div(self, value):
        return FakeTensor(self.array / value)

    def mul(self, value):
        return FakeTensor(self.array * value)

    def round(self):
        return FakeTensor(np.round(self.array))

    def clamp(self, low, high):
        return FakeTensor(np.clip(self.array, low, high))

    def permute(self, *axes):
        return FakeTensor(np.transpose(self.array, axes))

    def unsqueeze(self, axis):
        return FakeTensor(np.expand_dims(self.array, axis))

    def squeeze(self, axis):
        return FakeTensor(np.squeeze(self.array, axis))

    def cpu(self):
        return self

    def numpy(self):
        return self.array


@pytest.fixture
def fake_torch(monkeypatch):
    torch = types.ModuleType('torch')
    torch.uint8 = np.uint8
    torch.from_numpy = lambda array: FakeTensor(array)
    torch.no_grad = lambda: types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: False) \
        if False else _NoGrad()
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, 'torch', torch)
    return torch


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeModel:
    """An upscaler that repeats every pixel `scale` times in each direction."""
    dtype = np.float32
    device = 'cpu'
    architecture = 'FakeESRGAN'

    def __init__(self, scale=2):
        self.scale = scale
        self.calls = []

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        return self

    def __call__(self, tensor):
        self.calls.append(tensor.array.shape)
        out = tensor.array.repeat(self.scale, axis=2).repeat(self.scale, axis=3)
        return FakeTensor(out)


@pytest.fixture
def png(tmp_path, qapp):
    path = tmp_path / 'src.png'
    image = QtGui.QImage(5, 3, QtGui.QImage.Format.Format_RGB888)
    for x in range(5):
        for y in range(3):
            image.setPixelColor(x, y, QtGui.QColor(10 * x, 20 * y, 200))
    image.save(str(path))
    return path


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    monkeypatch.setattr(_upscale, '_model_cache', {})


class TestAvailability:
    def test_missing_packages_explain_how_to_install(self, monkeypatch):
        monkeypatch.setitem(sys.modules, 'torch', None)
        ok, message = _upscale.is_available()
        assert not ok and 'upscale' in message and 'torch' in message

    def test_available_when_everything_imports(self, monkeypatch):
        for name in ('torch', 'spandrel', 'huggingface_hub'):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        assert _upscale.is_available() == (True, '')


class TestModelPath:
    def test_local_override_skips_the_download(self, tmp_path, monkeypatch):
        weights = tmp_path / 'my.pth'
        weights.write_text('')
        monkeypatch.setenv('DIGICAM_ULTRASHARP_MODEL', str(weights))
        assert _upscale._model_path('ultrasharp') == weights

    def test_downloads_from_hugging_face_otherwise(self, tmp_path, monkeypatch):
        monkeypatch.delenv('DIGICAM_ULTRASHARP_MODEL', raising=False)
        hub = types.ModuleType('huggingface_hub')
        asked = []
        hub.hf_hub_download = lambda repo_id, filename: asked.append((repo_id, filename)) or str(tmp_path / filename)
        monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
        path = _upscale._model_path('ultrasharp')
        assert asked == [('Shandypur/ESRGAN-4x-UltraSharp', '4x-UltraSharp.pth')] and path.name == '4x-UltraSharp.pth'

    def test_a_bad_override_path_is_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DIGICAM_ULTRASHARP_MODEL', str(tmp_path / 'absent.pth'))
        hub = types.ModuleType('huggingface_hub')
        hub.hf_hub_download = lambda repo_id, filename: str(tmp_path / 'downloaded.pth')
        monkeypatch.setitem(sys.modules, 'huggingface_hub', hub)
        assert _upscale._model_path('ultrasharp').name == 'downloaded.pth'


class TestLoadModel:
    @pytest.fixture
    def spandrel(self, monkeypatch, fake_torch, tmp_path):
        module = types.ModuleType('spandrel')

        class ImageModelDescriptor:
            pass

        class Descriptor(ImageModelDescriptor, FakeModel):
            pass

        state = types.SimpleNamespace(loaded=[], model=Descriptor(), plain=False)

        class ModelLoader:
            def load_from_file(self, path):
                state.loaded.append(path)
                return object() if state.plain else state.model

        module.ImageModelDescriptor, module.ModelLoader = ImageModelDescriptor, ModelLoader
        monkeypatch.setitem(sys.modules, 'spandrel', module)
        monkeypatch.setattr(_upscale, '_model_path', lambda key: tmp_path / f'{key}.pth')
        return state

    def test_unknown_models_are_rejected(self):
        with pytest.raises(KeyError, match='Unknown upscale model'):
            _upscale._load_model('nope')

    def test_loads_once_and_uses_cuda_when_present(self, spandrel, fake_torch):
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: True)
        model = _upscale._load_model('ultrasharp')
        assert model is spandrel.model and model.device == 'cuda'
        assert _upscale._load_model('ultrasharp') is model and len(spandrel.loaded) == 1

    def test_uses_the_cpu_without_cuda(self, spandrel):
        assert _upscale._load_model('realesrgan_x4plus').device == 'cpu'

    def test_rejects_models_that_are_not_single_image(self, spandrel):
        spandrel.plain = True
        with pytest.raises(TypeError, match='not a single-image'):
            _upscale._load_model('ultrasharp')


class TestUpscaleImage:
    @pytest.fixture
    def model(self, monkeypatch, fake_torch):
        fake = FakeModel(scale=2)
        monkeypatch.setattr(_upscale, '_load_model', lambda key: fake)
        return fake

    def test_output_is_scaled_and_matches_the_source(self, model, png):
        result = _upscale.upscale_image(png, tile_size=2, tile_pad=1)
        assert (result.width(), result.height()) == (10, 6)
        assert result.pixelColor(0, 0) == QtGui.QColor(0, 0, 200)
        assert result.pixelColor(9, 5) == QtGui.QColor(40, 40, 200)       # last source pixel repeated 2x2
        assert result.pixelColor(2, 2) == QtGui.QColor(10, 20, 200)

    def test_tiles_are_padded_with_neighbouring_pixels(self, model, png):
        _upscale.upscale_image(png, tile_size=2, tile_pad=1)
        shapes = set(model.calls)
        assert len(model.calls) == 3 * 2 and (1, 3, 3, 3) in shapes          # an interior tile with padding

    def test_progress_and_cancellation(self, model, png):
        progress = []
        _upscale.upscale_image(png, tile_size=3, progress_cb=lambda done, total: progress.append((done, total)))
        assert progress == [(1, 2), (2, 2)]
        calls = {'n': 0}

        def cancel_after_first():
            calls['n'] += 1
            return calls['n'] > 1

        assert _upscale.upscale_image(png, tile_size=2, should_cancel=cancel_after_first) is None

    def test_unreadable_images_are_reported(self, model, tmp_path, qapp):
        bad = tmp_path / 'bad.png'
        bad.write_bytes(b'nope')
        with pytest.raises(ValueError, match='Could not read image'):
            _upscale.upscale_image(bad)
