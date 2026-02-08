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


def test_imports():
    # Top-level packages
    import deda
    import dedaverse

    # deda top-level module
    import deda.log

    # deda.ai
    import deda.ai
    # _neural_network requires torch (optional); continue test so other modules get coverage
    try:
        import deda.ai._neural_network  # noqa: F401
    except ModuleNotFoundError:
        pass

    # deda.core
    import deda.core
    import deda.core._app_launcher
    import deda.core._amazon_photos
    import deda.core._check_for_updates
    import deda.core._config
    import deda.core._photos
    import deda.core._plugin
    import deda.core._preferences
    import deda.core._types

    # deda.core.finder
    import deda.core.finder
    import deda.core.finder._adobe
    import deda.core.finder._houdini
    import deda.core.finder._maya
    import deda.core.finder._substance
    import deda.core.finder._unreal

    # deda.core.launcher
    import deda.core.launcher
    import deda.core.launcher._adobe
    import deda.core.launcher._houdini
    import deda.core.launcher._maya
    import deda.core.launcher._substance

    # deda.core.ai (optional: _model1, _usd_training require tensorflow)
    import deda.core.ai
    try:
        import deda.core.ai._model1  # noqa: F401
    except ModuleNotFoundError:
        pass
    try:
        import deda.core.ai._usd_training  # noqa: F401
    except ModuleNotFoundError:
        pass

    # deda.core.types
    import deda.core.types
    import deda.core.types._asset_id
    import deda.core.types._asset
    import deda.core.types._collection
    import deda.core.types._element
    import deda.core.types._entity
    import deda.core.types._project
    import deda.core.types._sequence
    import deda.core.types._shot

    # deda.core.viewer
    import deda.core.viewer
    import deda.core.viewer.__main__
    import deda.core.viewer._annotation
    import deda.core.viewer._app
    import deda.core.viewer._camera_reticle
    import deda.core.viewer._playbar
    import deda.core.viewer._reticle
    import deda.core.viewer._slate
    import deda.core.viewer._usd_viewer
    import deda.core.viewer._window

    # deda.model
    import deda.model
    import deda.model._types

    # deda.dcc
    import deda.dcc
    import deda.dcc._eventfilter

    # deda.plugins
    import deda.plugins.application_manager
    import deda.plugins.autodesk_flow
    import deda.plugins.godot
    import deda.plugins.houdini
    import deda.plugins.jira
    import deda.plugins.maya
    import deda.plugins.perforce
    import deda.plugins.photoshop
    import deda.plugins.plugin_manager
    import deda.plugins.project_manager
    import deda.plugins.substance
    import deda.plugins.zbrush

    # dedaverse
    import dedaverse.__main__

    # deda.app (requires PySide6; CI uses libEGL + QT_QPA_PLATFORM=offscreen)
    import deda.app
    import deda.app.__main__
    import deda.app._app
    import deda.app._asset_browser
    import deda.app._asset_info
    import deda.app._buttons
    import deda.app._dialogs
    import deda.app._eventfilter
    import deda.app._graphics_view
    import deda.app._main_window
    import deda.app._panel
    import deda.app._preferences
    import deda.app._project_settings
    import deda.app._taskbar_icon
    import deda.app.task
    import deda.app.task._task

    # Not importable (no package): deda.plugins.ollama
