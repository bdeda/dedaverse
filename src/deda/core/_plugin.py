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
__all__ = ['Plugin', 
           'Registry',
           'TaskManager',
           'NotificationSystem',
           'AssetManager',
           'DCCPlugin',
           ]


class Plugin:
    """Base class for all plugins."""
    
        
class Registry:
    """Plugin registry for holding all of the registered plugin instances at runtime.
    
    Plugin directories are found using the DEDAVERSE_PLUGIN_DIRS env variable.
    
    """


class TaskManager(Plugin):
    """Plugin for handliong task management system updates for the user.
    
    This interface provides the bridge for the sites task management system. This will 
    set status of the task when work starts or stops iteration, log time worked, and add
    comments based on state changes or whenever needed by the user. It will also be the 
    bridge for watching certain tasks and notify when watched tasks change state.
    
    """
    
class NotificationSystem(Plugin):
    """Plugin for handling notifications to a specific system. This can be as simple 
    as a log file, log server, or email. More involved notification systems can be 
    through slack, teams, or broadcast via a nework system to other dedaverse applications.
    
    """
    
    
class AssetManager(Plugin):
    """Plugin for handling the asset versioning systems used for a project. Typically 
    a project will have one storage system. Simple cases use a local or network drive.
    More complex systems allow versioning of files, like Perforce, or git. More complex 
    may have multiple versioning systems for different asset types, and the type will 
    identify the asset system it uses.
    
    """


class DCCPlugin(Plugin):
    """Plugin for launching a DCC application with the appropriate environment to expose
    the Dedaverse menu and tools. This also controls the entry points for generating the 
    interface for accessing the available tools and customizations for the application.
    
    """
    
    dcc_name = None   # must be defined in the derived plugin classes
    executable = None # must be set to the name of the executable to run
    