# ###################################################################################
#
# Copyright 2024 Ben Deda
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
"""
Application class definition, used for all Dedaverse tools run outside of other DCCs.
"""

__all__ = ["Application", "run"]


import os
import logging

from PySide6 import QtWidgets, QtCore

import deda.log
from ._main_window import MainWindow


log = logging.getLogger(__name__)


class Application(QtWidgets.QApplication):
    """Main application instance for all DedaFX apps."""

    def __init__(self, *args, **kwargs):        
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)
        super().__init__(*args, **kwargs)
        log.debug("Dedaverse main application created.")

        stylesheet = os.path.join(os.path.dirname(__file__), "stylesheet")
        with open(stylesheet, "r", encoding="utf-8") as f:
            style = f.read()
        self.setStyleSheet(style)


def run(loglevel='DEBUG'):
    """Run the main application."""
    deda.log.initialize(loglevel=loglevel)
    app = Application()
    w = MainWindow(app_name='Dedaverse')
    ret = app.exec_()
    log.warning(f'returning {ret}')
    return ret
    