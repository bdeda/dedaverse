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
import os
import logging

import deda.core
import deda.app

from PySide6 import QtWidgets, QtGui


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.plugin_manager')


DEFAULT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), 'plug.png')

class PluginWidget(QtWidgets.QWidget):
    
    DEFAULT_IMAGE = QtGui.QImage(DEFAULT_IMAGE_PATH)
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent=parent)
        
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if plugin.image:
            image = QtGui.QImage(plugin.image)
        else:
            image = self.DEFAULT_IMAGE
        title = f'{plugin.name} v{plugin.version}'
        description = plugin.description or '(No Description found)'
        
        image_lbl = QtWidgets.QLabel(parent=self)
        image_lbl.setPixmap(QtGui.QPixmap.fromImage(image))
        layout.addWidget(image_lbl, 0, 0, -1, 1)
        
        title_lbl = QtWidgets.QLabel(title, parent=self)  
        title_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(title_lbl, 0, 1, 1, -1)
        
        desc_lbl = QtWidgets.QLabel(description, parent=self)
        title_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(desc_lbl, 1, 1, -1, -1)        
        

class PluginManagerDialog(QtWidgets.QDialog):
    """UI for the plugin manager."""
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self._window_title_context = f"Plugin Manager [deda@{__version__}]"
        self.setWindowTitle(self._window_title_context)
        self.setModal(True)
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        vbox.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QtWidgets.QScrollArea(parent=self)
        vbox.addWidget(scroll_area)
        central_widget = QtWidgets.QWidget(parent=self)
        scroll_area.setWidget(central_widget)
        scroll_area.setWidgetResizable(True)
        plugin_list = QtWidgets.QVBoxLayout(central_widget)
        central_widget.setLayout(plugin_list)
        
        # list of all installed plugins
        for plugin in deda.core.PluginRegistry():
            plugin_list.addWidget(PluginWidget(plugin, parent=self))
            
        plugin_list.addStretch()
        
        # check state to load/unload a plugin
        
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
        
    
    def load(self):
        """Load the plugin."""
        
        log.info('Dedaverse Plugin Manager loading...')
        
        # Create the menu to launch the tool, then wire up the launch
        # method to handle opening the modal tool window.
        
        menu = deda.app.get_main_menu()
        first_action = None
        for action in menu.actions():
            first_action = action
            break
        show_action = QtGui.QAction('Plugins', parent=menu)
        show_action.triggered.connect(self.launch)
        if first_action:
            menu.insertAction(first_action, show_action)
        else:
            menu.addAction(show_action)
            
        log.info('Plugin Manager loaded successfully.')
        
        
deda.core.PluginRegistry().register(PluginManager('Plugin Manager', __version__, __vendor__))