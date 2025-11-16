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
"""
Application class definition, used for all Dedaverse tools run outside of other DCCs.
"""

__all__ = ["Application", "run", "get_proc_under_mouse", "is_venv"]


import sys
import logging
try:
    import win32gui
    import win32process
except ImportError:
    pass
import psutil
import ctypes

from PySide6 import QtWidgets, QtCore

import deda.log
import deda.core
from ._main_window import MainWindow


log = logging.getLogger(__name__)


class Application(QtWidgets.QApplication):
    """Main application instance for all DedaFX apps."""

    def __init__(self, *args, **kwargs): 
        # For UI scaling
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)
        super().__init__(['-platform', 'windows:darkmode=2'], **kwargs)
        self.setStyle('Fusion')        
        myappid = u'dedafx.dedaverse.0.1.0' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        log.debug("Dedaverse main application created.")


def run(loglevel='DEBUG'):
    """Run the main application."""
    deda.log.initialize(loglevel=loglevel)
    deda.core.initialize()
    app = Application()
    w = MainWindow(app_name='Dedaverse')
    # This needs to happen after the main window is created because the load calls may b emodifying the UIs.
    for plugin in deda.core.PluginRegistry():
        try:
            plugin.load()
        except Exception as err:
            log.exception(err)
    ret = app.exec_()
    log.debug(f'Returning {ret}')
    return ret


def get_proc_under_mouse():
    """Get the process under the mouse on Windows."""
    hwnd = win32gui.WindowFromPoint(win32gui.GetCursorPos())
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid)
    except Exception as err:
        log.error(err)


def is_venv():
    """If this process is a virtual env or not."""
    return sys.prefix != sys.base_prefix