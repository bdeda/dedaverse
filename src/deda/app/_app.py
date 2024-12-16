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

__all__ = ["Application", "run", "get_top_window", "get_main_menu"]


import os
import logging
import functools

from PySide6 import QtWidgets, QtCore

import deda.log
import deda.core
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


@functools.lru_cache
def get_top_window():
    """Retrun the top window of the application to use as a parent for other tool windows.
    
    Returns:
        QWidget
        
    """
    for top_window in QtWidgets.QApplication.instance().topLevelWidgets():
        if top_window.objectName() in ('DedaverseMainWindow', 'MayaWindow'):
            return top_window
        
        
@functools.lru_cache
def get_main_menu():
    """Get the main menu for the app. When this is running as the standalone dedaverse app
    in the windows system tray, this will return the main context menu instance. In the
    DCC applications, thisi will be the main dedaverse menu.
    
    Returns:
        QMenu
    
    """
    window = get_top_window()
    for child in window.children():
        if not isinstance(child, QtWidgets.QMenu):
            continue
        if child.objectName() == 'DedaverseTaskbarContextMenu':
            return child
    