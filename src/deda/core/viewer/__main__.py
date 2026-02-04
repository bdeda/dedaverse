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
"""Main entry point for the Dedaverse viewer application."""

from pathlib import Path

from deda.app import Application
from deda.app import _main_window as _app_main_window
from deda.core.viewer import _window
from PySide6 import QtGui

if __name__ == '__main__':
    app = Application()
    icon_path = Path(_app_main_window.__file__).parent / 'icons' / 'star_icon.png'
    if icon_path.is_file():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    w = _window.MainWindow()
    w.show()
    app.exec()