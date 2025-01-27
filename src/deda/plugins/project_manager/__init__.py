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
The Project Manager is the tool for creating a new project, selecting the project
that is being worked on, and configuring the selected project. It saves a project 
config file in the users dedaverse dir.

User configs can be useed to include other locations for project configs, and those 
locations can be found using the Project Manager tool too.

"""
import os
import logging

import deda.core
import deda.app

from PySide6 import QtWidgets, QtGui


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.project_manager')


#DEFAULT_IMAGE_PATH = os.path.join(os.path.dirname(__file__), 'plug.png')

#class PluginWidget(QtWidgets.QWidget):
    
    #DEFAULT_IMAGE = QtGui.QImage(DEFAULT_IMAGE_PATH)
    
    #def __init__(self, plugin, parent=None):
        #super().__init__(parent=parent)
        
        #layout = QtWidgets.QGridLayout()
        #self.setLayout(layout)
        #layout.setContentsMargins(0, 0, 0, 0)
        
        #if plugin.image:
            #image = QtGui.QImage(plugin.image)
        #else:
            #image = self.DEFAULT_IMAGE
        #title = f'{plugin.name} v{plugin.version}'
        #description = plugin.description or '(No Description found)'
        
        #image_lbl = QtWidgets.QLabel(parent=self)
        #image_lbl.setPixmap(QtGui.QPixmap.fromImage(image))
        #layout.addWidget(image_lbl, 0, 0, -1, 1)
        
        #title_lbl = QtWidgets.QLabel(title, parent=self)  
        #title_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        #layout.addWidget(title_lbl, 0, 1, 1, -1)
        
        #desc_lbl = QtWidgets.QLabel(description, parent=self)
        #title_lbl.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        #layout.addWidget(desc_lbl, 1, 1, -1, -1)        
        

class ProjectManagerDialog(QtWidgets.QDialog):
    """UI for the project manager."""
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        
        self._window_title_context = f"Project Manager [deda@{__version__}]"
        self.setWindowTitle(self._window_title_context)
        self.setModal(True)
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        #vbox.setContentsMargins(0, 0, 0, 0)
        
        # Project: <project name>, combobox with autocomplete
        
        vbox.addWidget(QtWidgets.QLabel('Current Project:'))
        vbox.addStretch()
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        vbox.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
    def accept(self):
        log.info('Project settings saved.')
        super().accept()
        


class ProjectManager(deda.core.Tool):
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
        return ProjectManagerDialog(parent=parent)
        
    
    def load(self):
        """Load the plugin."""
        
        log.info('Project Manager loading...')
        
        # Create the menu to launch the tool, then wire up the launch
        # method to handle opening the modal tool window.
        
        menu = deda.app.get_main_menu()
        first_action = None
        for action in menu.actions():
            first_action = action
            break
        show_action = QtGui.QAction('Project', parent=menu)
        show_action.triggered.connect(self.launch)
        if first_action:
            menu.insertAction(first_action, show_action)
        else:
            menu.addAction(show_action)
            
        log.info('Project Manager loaded successfully.')
        
        
#deda.core.PluginRegistry().register(ProjectManager('Project Manager', __version__, __vendor__))