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

"""Import unittests for deda and dedaverse.

These tests only import modules; they do not use the network or external services.
Run with: python -m pytest tests/test_imports.py -v
"""

import unittest


def _import_deda_and_dedaverse() -> None:
    """Top-level packages and deda.log."""
    import deda  # noqa: F401
    import dedaverse  # noqa: F401
    import deda.log  # noqa: F401
    import deda.ai  # noqa: F401
    try:
        import deda.ai._neural_network  # noqa: F401
    except ModuleNotFoundError:
        pass
    import dedaverse.__main__  # noqa: F401


def _import_deda_core() -> None:
    """deda.core and subpackages (finder, launcher, types, ai, viewer)."""
    import deda.core  # noqa: F401
    import deda.core._app_launcher  # noqa: F401
    try:
        import deda.core._amazon_photos  # noqa: F401
    except ModuleNotFoundError:
        pass
    import deda.core._check_for_updates  # noqa: F401
    import deda.core._config  # noqa: F401
    try:
        import deda.core._photos  # noqa: F401
    except ModuleNotFoundError:
        pass
    import deda.core._plugin  # noqa: F401
    import deda.core._preferences  # noqa: F401
    import deda.core._types  # noqa: F401
    import deda.core.finder  # noqa: F401
    import deda.core.finder._adobe  # noqa: F401
    import deda.core.finder._houdini  # noqa: F401
    import deda.core.finder._maya  # noqa: F401
    import deda.core.finder._substance  # noqa: F401
    import deda.core.finder._unreal  # noqa: F401
    import deda.core.launcher  # noqa: F401
    import deda.core.launcher._adobe  # noqa: F401
    import deda.core.launcher._houdini  # noqa: F401
    import deda.core.launcher._maya  # noqa: F401
    import deda.core.launcher._substance  # noqa: F401
    import deda.core.ai  # noqa: F401
    try:
        import deda.core.ai._model1  # noqa: F401
    except ModuleNotFoundError:
        pass
    try:
        import deda.core.ai._usd_training  # noqa: F401
    except ModuleNotFoundError:
        pass
    import deda.core.types  # noqa: F401
    import deda.core.types._asset_id  # noqa: F401
    import deda.core.types._asset  # noqa: F401
    import deda.core.types._collection  # noqa: F401
    import deda.core.types._element  # noqa: F401
    import deda.core.types._entity  # noqa: F401
    import deda.core.types._project  # noqa: F401
    import deda.core.types._sequence  # noqa: F401
    import deda.core.types._shot  # noqa: F401
    try:
        import deda.core.viewer  # noqa: F401
        import deda.core.viewer.__main__  # noqa: F401
        import deda.core.viewer._annotation  # noqa: F401
        import deda.core.viewer._app  # noqa: F401
        import deda.core.viewer._camera_reticle  # noqa: F401
        import deda.core.viewer._playbar  # noqa: F401
        import deda.core.viewer._reticle  # noqa: F401
        import deda.core.viewer._slate  # noqa: F401
        import deda.core.viewer._usd_viewer  # noqa: F401
        import deda.core.viewer._window  # noqa: F401
    except (ModuleNotFoundError, ImportError):
        pass


def _import_deda_model_dcc() -> None:
    """deda.model and deda.dcc."""
    import deda.model  # noqa: F401
    import deda.model._types  # noqa: F401
    import deda.dcc  # noqa: F401
    import deda.dcc._eventfilter  # noqa: F401


def _import_deda_plugins() -> None:
    """deda.plugins (no network; optional plugins may be skipped)."""
    import deda.plugins.application_manager  # noqa: F401
    import deda.plugins.autodesk_flow  # noqa: F401
    import deda.plugins.godot  # noqa: F401
    import deda.plugins.houdini  # noqa: F401
    import deda.plugins.jira  # noqa: F401
    import deda.plugins.maya  # noqa: F401
    import deda.plugins.perforce  # noqa: F401
    import deda.plugins.photoshop  # noqa: F401
    import deda.plugins.plugin_manager  # noqa: F401
    import deda.plugins.project_manager  # noqa: F401
    import deda.plugins.substance  # noqa: F401
    import deda.plugins.zbrush  # noqa: F401


def _import_deda_app() -> None:
    """deda.app (PySide6; no network)."""
    import deda.app  # noqa: F401
    import deda.app.__main__  # noqa: F401
    import deda.app._app  # noqa: F401
    import deda.app._asset_browser  # noqa: F401
    import deda.app._asset_info  # noqa: F401
    import deda.app._buttons  # noqa: F401
    import deda.app._dialogs  # noqa: F401
    import deda.app._eventfilter  # noqa: F401
    import deda.app._graphics_view  # noqa: F401
    import deda.app._main_window  # noqa: F401
    import deda.app._panel  # noqa: F401
    import deda.app._preferences  # noqa: F401
    import deda.app._project_settings  # noqa: F401
    import deda.app._taskbar_icon  # noqa: F401
    import deda.app.task  # noqa: F401
    import deda.app.task._task  # noqa: F401


def test_imports() -> None:
    """Run all import checks (no network)."""
    _import_deda_and_dedaverse()
    _import_deda_core()
    _import_deda_model_dcc()
    _import_deda_plugins()
    _import_deda_app()


class TestImports(unittest.TestCase):
    """Import unittests: verify modules import without network or external services."""

    def test_import_deda_and_dedaverse(self) -> None:
        _import_deda_and_dedaverse()

    def test_import_deda_core(self) -> None:
        _import_deda_core()

    def test_import_deda_model_dcc(self) -> None:
        _import_deda_model_dcc()

    def test_import_deda_plugins(self) -> None:
        _import_deda_plugins()

    def test_import_deda_app(self) -> None:
        _import_deda_app()

    def test_imports_full(self) -> None:
        """Full import pass (same as running all granular tests)."""
        test_imports()
