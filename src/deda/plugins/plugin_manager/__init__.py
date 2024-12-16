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
The Plugin Manager is a UI and logic for gathering available plugins from a specified
list of git repos. These repos can be public facing or a private corporate enterprise 
repo only available to internal employees.

"""
import logging
import functools

import deda.core
import deda.app

from PySide6 import QtWidgets, QtGui


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.plugin_manager')


class PluginManagerDialog(QtWidgets.QDialog):
    """UI for the plugin manager."""
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self._window_title_context = f"Plugin Manager [deda@{__version__}]"
        self.setWindowTitle(self._window_title_context)
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        vbox.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QtWidgets.QScrollArea(parent=self)
        vbox.addWidget(scroll_area)
        
        # list of all installed plugins
        
        # Button to search internet for available plugins
        


class PluginManager(deda.core.Tool):
    """Tool for managing plugin installations. 
    
    This UI will show the list of available plugins, the installed plugins, and 
    show which plugin version is installed and if it can/should be updated.
    
    """
    
    def initialize_window(self, parent):
        """Initialize the tool window. This will be called only once
        to construct the UI when it is first shown.
        
        Returns:
            QWidget
            
        """
        return PluginManagerDialog(parent=parent)
        #w = QtWidgets.QDialog(parent=parent)
        #w.setModal(True)
        #return w
        
    
    def load(self):
        """Load the plugin."""
        
        log.info('Dedaverse Plugin Manager plugin loading...')
        
        # Create the menu to launch the tool, then wire up the launch
        # method to handle opening the modal tool window.
        
        menu = deda.app.get_main_menu()
        first_action = None
        for action in menu.actions():
            first_action = action
            break
        show_action = QtGui.QAction('Plugin Manager', parent=menu)
        show_action.triggered.connect(self.launch)
        if first_action:
            menu.insertAction(first_action, show_action)
        else:
            menu.addAction(show_action)
            
        log.info('Plugin Manager loaded successfully.')
        
        
        
        
        
deda.core.PluginRegistry().register(PluginManager('Dedaverse Plugin Manager', __version__, __vendor__))