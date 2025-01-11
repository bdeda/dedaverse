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
__all__ = ['initialize_plugins',
           'Plugin', 
           'PluginRegistry',
           'Tool', 
           'TaskManager',
           'NotificationSystem',
           'AssetManager',
           'DCCPlugin',
           ]

import os
import sys
import logging
import pkgutil
from collections import OrderedDict
import packaging.version
import subprocess


log = logging.getLogger(__name__)


def initialize_plugins():
    """Do the initial import os all of the plugin modules but do not load the plugin instances yet."""
    paths = os.getenv('DEDAVERSE_PLUGIN_DIRS')
    if not paths:
        paths = []
    else:
        paths = paths.split(os.pathsep)
    
    standard_plugin_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'plugins'))
    paths.insert(0, standard_plugin_path)
           
    for loader, module_name, is_pkg in pkgutil.walk_packages(paths):
        if f'dedaverse.plugins.{module_name}' in sys.modules:
            log.warning('Plugin named "{}" is already loaded! Skipoping...'.format(module_name))
            continue
        log.debug('Loading {}'.format(module_name))
        try:
            spec = loader.find_spec(module_name, loader.path)
            module = spec.loader.load_module(module_name)
            sys.modules[f'dedaverse.plugins.{module_name}'] = module
            # The loading of the module should have registered the plugin with the deda.core.PluginRegistry
            log.debug(module)
        except Exception as err:
            log.exception(err)


class Plugin:
    """Base class for all plugins."""
    
    def __init__(self, name, 
                 version=None, 
                 vendor=None, 
                 description=None, 
                 image=None, 
                 *args, **kwargs):
        self._name = name
        self._version = None
        if version:
            self._version = packaging.version.parse(version)
        self._vendor = vendor
        self._description = description or ''
        self._image = image
        
    @property
    def description(self):
        return self._description
    
    @property
    def image(self):
        return self._image    
        
    @property
    def name(self):
        return self._name
    
    @property
    def vendor(self):
        return self._vendor    
    
    @property
    def version(self):
        return self._version
    
    def load(self):
        """Override in derived classes to handle the loading process for the plugin.
        
        This load call should gather all of the relative env settings or configuration 
        data to properly set up the plugin for use with the system.
        
        Returns:
            (bool) True or False if the load call was successful.
            
        """
        raise NotImplementedError        
    
        
class PluginRegistry:
    """Plugin registry for holding all of the registered plugin instances at runtime.
    
    Plugin directories are found using the DEDAVERSE_PLUGIN_DIRS env variable.
    
    """
    
    _registry_ = OrderedDict()
    
    def register(self, plugin):
        """Register a plugin to the system.
        
        Args:
            plugin: (Plugin) The plugin type.
            
        """
        PluginRegistry._registry_[plugin.name] = plugin
        
    def get(self, plugin_name):
        """Return the plugin with the given name is found in the registry. Otherwise return None.
        
        Args:
            plugin_name: (str) The plugin name.
            
        Returns:
            Plugin: The instance of the plugin object.
            
        """
        return PluginRegistry._registry_.get(plugin_name)
        
    def __iter__(self):
        """Iterate on all pluginins in the registry."""
        for item in self._registry_.values():
            yield item
            
    def iter_plugins(self, plugin_type):
        """Iterate over the plugins of a given type.
        
        Yields:
            Plugin instance if the plugin isinstance of the given type.
            
        """
        for plugin in self:
            if isinstance(plugin, plugin_type):
                yield plugin
            
            
class Tool(Plugin):
    """This plugin is a UI and contains it's own logic for managing the functionality of the tool.
    
    The UI should not be defined in the plugin __init__, but should be instantiated, or shown in the overriden launch method.
    
    """
    
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self._window_instance = None
    
    def initialize_window(self, parent):
        """Override in the derived classes to initialize the widget for this plugin."""
        raise NotImplementedError
       
    def launch(self):
        """Construct the UI or find the appropriate instance and show."""
        if not self._window_instance:
            import deda.app
            parent_window = deda.app.get_top_window()
            self._window_instance = self.initialize_window(parent=parent_window)
        self._window_instance.show()
        self._window_instance.raise_()
        self._window_instance.activateWindow()


class TaskManager(Plugin):
    """Plugin for handliong task management system updates for the user.
    
    This interface provides the bridge for the sites task management system. This will 
    set status of the task when work starts or stops iteration, log time worked, and add
    comments based on state changes or whenever needed by the user. It will also be the 
    bridge for watching certain tasks and notify when watched tasks change state.
    
    """
    
    def get_task(self, search_criteria):
        """Get a task from the server."""
        raise NotImplementedError
    
    def update_task(self, task):
        """Update the given task on the server. 
        This commits any local changes to the task management server.
        
        """
        raise NotImplementedError    
    
    
class NotificationSystem(Plugin):
    """Plugin for handling notifications to a specific system. This can be as simple 
    as a log file, log server, or email. More involved notification systems can be 
    through slack, teams, or broadcast via a nework system to other dedaverse applications.
    
    """
    
    def notify(self, title, message, level='info', *args, **kwargs):
        """Notify the necesary subsystems with the given message. 
        Depending on the notificatiuon system, this can show a popup window, 
        a status message in the main window, log to disk, email, slack, etc.
        
        """
        raise NotImplementedError
    
    
class AssetManager(Plugin):
    """Plugin for handling the asset versioning systems used for a project. Typically 
    a project will have one storage system. Simple cases use a local or network drive.
    More complex systems allow versioning of files, like Perforce, or git. More complex 
    may have multiple versioning systems for different asset types, and the type will 
    identify the asset system it uses.
    
    """
    
    def can_handle(self, assets):
        """Check to see if the given assets are the types of assets this plugin can handle. 
        
        Args:
            assets: (Assets) The asset to check.
            
        Returns:
            list: The list of bools on if the asset can be handles by this plugin.
            
        """
        raise NotImplementedError
    
    
    def add(self, assets):
        """Add assets to the asset system.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            
        """
        raise NotImplementedError
    
    def rename(self, asset, new_name):
        """Rename an asset in the asset system.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            new_name: (str) The new name for the asset.
            
        """
        raise NotImplementedError
    
    def delete(self, assets):
        """Delete assets from the asset system.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            
        """
        raise NotImplementedError
    
    def get_latest(self, assets):
        """Get the latest version of assets from the asset system.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            
        """
        raise NotImplementedError 
    
    def get_version(self, asset, version):
        """Get the given version of an asset from the asset system.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            version: (int) The version number.
            
        """
        raise NotImplementedError    
    
    def checkout(self, assets):
        """Checkout the assets from the asset system. This is an exclusive checkout.
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            
        """
        raise NotImplementedError
    
    def commit(self, assets, message):
        """Commit the assets to the asset system. 
        
        Args: 
            asset: (Asset) Add an asset to the asset system.
            message: (str) The commit message for this asset
            
        """
        raise NotImplementedError    


class DCCPlugin(Plugin):
    """Plugin for launching a DCC application with the appropriate environment to expose
    the Dedaverse menu and tools. This also controls the entry points for generating the 
    interface for accessing the available tools and customizations for the application.
    
    """
    
    def __init__(self, dcc_name=None,   # must be defined in the derived plugin classes
                 executable=None, # must be set to the name of the executable to run
                 *args, **kwargs):
        super().__init__(dcc_name, *args, **kwargs)
        self._executable = executable
        
    def find(self):
        """Find the DCC using the plugin logic to check normal install locations, env vars, etc.
        This should be overriden in the plugin implementation to find and self.set_executable(path).
        
        Returns:
            (str) Full path of executable found.
        
        """
        raise NotImplementedError
    
    def set_executable(self, executable):
        """Set the executable string to use when launching this DCC.
        
        Args:
            executable: (str) The full path to the executable.
            
        Returns:
            None
            
        """
        if not isinstance(executable, str):
            raise TypeError(f'Executable must be a string. Got {type(executable)}')
        self._executable = executable
        
    def setup_env(self, env):
        """Override in the plugin to modify the env for the subprocess.
        
        Args:
            env: (dict) The original env.
        
        Returns:
            dict: The modified version of env.
            
        """
        return env
    
    def launch(self, *args, **kwargs):
        """Launch the dcc application with the appropriate environment using the given args.
        
        """
        # TODO: Check if this needs to be wrapped in quotes or not, depending on the system.
        cmd = [f'"{self._executable}"']
        for arg in args:
            cmd.append(arg)
        for key, value in kwargs.items():
            cmd.append(f'{key}={value}')
        dcc_env = os.environ.copy()
        # modify env if required for the subprocess
        dcc_env = self.setup_env()
        return subprocess.run(cmd, capture_output=True, env=dcc_env)