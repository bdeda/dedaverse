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
The Project Manager is the tool for creating a new project, selecting the project
that is being worked on, and configuring the selected project. It saves a project 
config file in the users dedaverse dir.

User configs can be useed to include other locations for project configs, and those 
locations can be found using the Project Manager tool too.

"""
import os
import logging

import deda.core


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.godot')


class Godot(deda.core.Application):
    """Godot is an open source game engine. This plugin will find/configure/download and install
    the Godot game engine and configure it as an application for use by the dedaverse system.
    
    """
    
    icon_path = os.path.join(os.path.dirname(__file__), 'godot_icon_128.png')
    
    def load(self):
        """Load the plugin."""
        
        log.info('Godot plugin loading...')
        
        # Create the menu to launch the tool, then wire up the launch
        # method to handle opening the modal tool window.
        
        #menu = deda.app.get_main_menu()
        #first_action = None
        #for action in menu.actions():
            #first_action = action
            #break
        #show_action = QtGui.QAction('Project', parent=menu)
        #show_action.triggered.connect(self.launch)
        #if first_action:
            #menu.insertAction(first_action, show_action)
        #else:
            #menu.addAction(show_action)
            
        log.info('Godot loaded successfully.')
        
        
deda.core.PluginRegistry().register(Godot('Godot', __version__, __vendor__, 
                                          image=Godot.icon_path, 
                                          description=Godot.__doc__))