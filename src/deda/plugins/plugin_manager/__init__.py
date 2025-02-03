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

from PySide6 import QtWidgets, QtGui, QtCore


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.plugin_manager')


DEFAULT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), 'plug.png')

class PluginWidget(QtWidgets.QFrame):
    """Widget for a single plugin."""
    
    DEFAULT_IMAGE = QtGui.QImage(DEFAULT_IMAGE_PATH)
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent=parent)
        
        self._plugin = plugin
        self.setMouseTracking(True)
        #self.setAttribute(QtCore.Qt.WA_HOVER, True)
        
        self.setStyleSheet("PluginWidget{background-color: rgba(20,20,20,255);"
                           "border: 1px solid rgb(40,40,40); border-radius: 5px;}")
        if True: #self._plugin.loaded:
            self.setStyleSheet("PluginWidget{background-color: rgba(20,20,20,128);"
                               "border: 1px solid rgb(40,40,40); border-radius: 5px;}")
        
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)        
        if plugin.image and os.path.isfile(plugin.image):
            image = QtGui.QImage(plugin.image)
        else:
            image = self.DEFAULT_IMAGE
        title = f'{plugin.name} v{plugin.version}'
        description = plugin.description or '(No Description found)'
        
        image_lbl = QtWidgets.QLabel(parent=self)
        pix = QtGui.QPixmap.fromImage(image)
        image_lbl.setPixmap(pix)
        effect = QtWidgets.QGraphicsColorizeEffect(image_lbl)
        effect.setStrength(1.0)
        effect.setColor(QtGui.QColor('silver'))        
        layout.addWidget(image_lbl, 0, 0, -1, 1)
        
        self._title_lbl = QtWidgets.QLabel(title, parent=self)  
        layout.addWidget(self._title_lblself._title_lbl, 0, 1, 1, -1)
        
        self._desc_lbl = QtWidgets.QLabel(description, parent=self)
        layout.addWidget(self._desc_lbl, 1, 1)
        
        layout.setColumnMinimumWidth(0, image.width())
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(parent=self)
        
        action = menu.addAction('Check for Updates')
        
        menu.exec_(self.mapToGlobal(pos))
        
    def enterEvent(self, event):
        self.setStyleSheet("PluginWidget{background-color: rgba(20,20,20,255);"
                           "border: 1px solid rgb(40,40,40); border-radius: 5px;}")
    
    def leaveEvent(self, event):
        if not self._plugin.loaded:
            self.setStyleSheet("PluginWidget{background-color: rgba(20,20,20,128);"
                               "border: 1px solid rgb(40,40,40); border-radius: 5px;}")
        
    def mouseReleaseEvent(self, event):
        """Handle the click"""
        if event.button() == QtCore.Qt.LeftButton:
            self._plugin._loaded = not self._plugin._loaded
            if self._plugin.loaded:
                self.enterEvent(None)
            else:
                self.enterEvent(None)
        return super().mouseReleaseEvent(event)
        
        
    
        

class PluginManagerDialog(QtWidgets.QDialog):
    """UI for the plugin manager.
    Allows the user to load and unload plugins available for the current project.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self._window_title_context = f"Plugin Manager [deda@{__version__}]"
        self.setWindowTitle(self._window_title_context)
        self.setModal(True)
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
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
        if hasattr(parent, 'current_project'):
            if not parent.current_project:
                log.error('Choose a project before configuring the plugins for the project.')
                return
            if not parent.current_project.is_writable:
                log.error('Project cannot be modified. The config file is not writable.')
                return
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
        
        
deda.core.PluginRegistry().register(PluginManager('Plugin Manager', __version__, __vendor__,
                                                  description=PluginManager.__doc__))