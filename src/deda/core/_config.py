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
"""Layered config."""

__all__ = ['LayeredConfig', 'ProjectConfig']

import os
import json
import logging

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json


log = logging.getLogger(__name__)


@dataclass_json
@dataclass(eq=False) 
class AppConfig:
    
    name: str
    version: str
    command: str
    icon_path: str
    
    install_url: str
    help_url: str
    enabled: bool
    
    def __eq__(self, other):
        return self.name == other.name and self.version == other.version
    
    def __hash__(self):
        return hash(self.name, self.version)
    

@dataclass_json
@dataclass(eq=False)
class PluginConfig:
    
    name: str
    version: str
    enabled: bool
    installed: bool
    url: str
    
    def __eq__(self, other):
        return self.name == other.name and self.version == other.version 
    
    def __hash__(self):
        return hash(self.name, self.version)    
    

@dataclass_json
@dataclass(eq=False)
class ServiceConfig:
    
    name: str
    enabled: bool
    url: str
    params: list[str] = field(default_factory=list)
    
    def __eq__(self, other):
        # We compare name only because we do not want projects and users 
        # to be able to override the services with their own (ie, Perforce, Jira, etc.)
        return self.name == other.name  
    
    def __hash__(self):
        return hash(self.name, self.version)    
    

@dataclass_json
@dataclass
class SiteConfig:
    
    # studio name or user name 
    name: str | None = None
    
    # urls to use for dataverse plugin discovery and updates, in priority order
    plugin_urls: list[str] = field(default_factory=list)
    
    plugins: list[PluginConfig] = field(default_factory=list)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)
    projects: dict[str, str] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.name) 
    
    @classmethod
    def load(cls):
        site_config_path = os.getenv('DEDAVERSE_SITE_CONFIG')
        if not site_config_path:
            return        
        if os.path.isfile(site_config_path):
            with open(site_config_path, 'r') as f:
                data = f.read()
            return cls.from_json(data)            
        return cls()
    
    def save(self):
        site_config_path = os.getenv('DEDAVERSE_SITE_CONFIG')
        if not site_config_path:
            return
        site_config_dir = os.path.dirname(site_config_path)
        try:
            os.makedirs(site_config_dir)
        except OSError:
            pass
        # TODO: check if we can write to the file
        with open(site_config_path, 'w') as f:
            f.write(self.to_json())    


@dataclass_json
@dataclass
class ProjectConfig:
    """The project configuration data."""
    
    name: str      # name identifier   
    rootdir: str  # This is where all of the project files will go on the local disk
    
    cfg_path: str | None = None # defaults to "{project.rootdir}/.dedaverse/project.cfg"    
    key: str | None = None    # short name, optional like FEN 
    
    # The type of project that this is. This is used to map to lists of 
    # asset types available for the project during initial creation.
    project_type: str | None = None
    
    # The list of asset types used in this project
    asset_types: list[str] = field(default_factory=list)
    
    # The list of plugins for use in the Project.
    plugins: list[PluginConfig] = field(default_factory=list)  
    
    # services are meant to be rest-based services that are parameterized and  
    # have a clear API that can be leveraged from within a simple interface.
    services: list[str] = field(default_factory=list)
    
    # The list of applications for use in this project. 
    # Typically this will be specific versions of applications, and they will be exposed in the Apps panel.
    apps: list[AppConfig] = field(default_factory=list) 
    
    def __eq__(self, other):
        return self.name == str(other) 
    
    def __hash__(self):
        return hash(self.name)  
    
    def __str__(self):
        return self.name
    
    @classmethod
    def load(cls, path):
        if not path:
            log.error('Project must have a config path to load from.')
            return        
        if not os.path.isfile(path):
            log.error(f'Project config path is not a file that exists. {path}')
            return
        with open(path, 'r') as f:
            data = f.read()
        project = cls.from_json(data) 
        # Ensure future saves will go to the same file on disk.
        project.cfg_path = path
        return project
    
    def save(self):
        if not self.cfg_path:
            log.error('Cannot save the project config file because cfg_path is not set.')
            return
        project_config_dir = os.path.dirname(self.cfg_path)
        try:
            os.makedirs(project_config_dir)
        except OSError:
            pass
        # TODO: check if we can write to the file
        with open(self.cfg_path, 'w') as f:
            f.write(self.to_json())    
    
    
@dataclass_json
@dataclass 
class UserConfig:
    """The user configuration data."""
    
    current_project: str | None = None
    projects: dict[str, str] = field(default_factory=dict)
    roles: list[str] = field(default_factory=list) # animator, rigger, concept artist, etc
    
    plugins: list[PluginConfig] = field(default_factory=list)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)
    
    @classmethod
    def load(cls):
        user_config_path = os.path.expanduser('~/.dedaverse/user.cfg')
        if os.path.isfile(user_config_path):
            with open(user_config_path, 'r') as f:
                data = f.read()
            return cls.from_json(data)            
        return cls()
    
    def save(self):
        user_config_path = os.path.expanduser('~/.dedaverse/user.cfg')
        user_config_dir = os.path.expanduser('~/.dedaverse')
        try:
            os.makedirs(user_config_dir)
        except OSError:
            pass
        with open(user_config_path, 'w') as f:
            f.write(self.to_json())
    

class LayeredConfig:
    
    def __init__(self):
        
        self._all_projects = {}
        
        # The site config is loaded to include the settings for all users and all projects
        # This is retrieved via env var, and set up by system administrators or pipeline teams
        self._site_config = SiteConfig.load()
               
        # Loaded first, when the system starts. If not found, opens up a <new project>
        self._user_config = UserConfig.load()
               
    @property
    def user(self):
        return self._user_config
    
    @property
    def current_project(self):
        return self.user.current_project
    
    @current_project.setter
    def current_project(self, project):
        if project not in self.projects:
            raise ValueError(f'Project {project} is not in the user config list of available projects!')
        if project not in self.user.projects:
            # we should only get here if the project is not defined at the site level
            self.user.projects.append(project)        
        self.user.current_project = str(project) 
        
    @property
    def projects(self):
        for project in self.user.projects:
            yield project
            
    def save(self):
        self._user_config.save()
        if self._site_config:
            self._site_config.save()
        