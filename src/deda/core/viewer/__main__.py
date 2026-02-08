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

import sys
from pathlib import Path
import logging

import click
from PySide6 import QtCore, QtGui

import deda.log
from deda.app import Application
from deda.app import _main_window as _app_main_window
from deda.core.viewer import _window


log = logging.getLogger('deda.core.viewer')


@click.command()
@click.argument('usd_path', required=False, type=click.Path(exists=False))
def viewer(usd_path):
    """Run the Dedaverse viewer, optionally opening a USD file.

    USD_PATH is an optional path to a USD file (.usd, .usda, .usdc, .usdz)
    to open when the viewer starts.
    """
    deda.log.initialize(loglevel=logging.INFO)
    app = Application()
    icon_path = Path(_app_main_window.__file__).parent / 'icons' / 'star_icon.png'
    if icon_path.is_file():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    w = _window.MainWindow()
    w.show()
    if usd_path:
        path_str = str(Path(usd_path).resolve())
        QtCore.QTimer.singleShot(0, lambda: w._open_stage_file(path_str))
    return app.exec()


if __name__ == '__main__':
    sys.exit(viewer())