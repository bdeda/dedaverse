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
"""Layered configuration system for Dedaverse.

Configuration is layered in priority order (later layers override earlier):
1. **Site config** - System-wide settings from ``DEDAVERSE_SITE_CONFIG`` env var.
   Used by system administrators or pipeline teams.
2. **User config** - Per-user settings at ``~/.dedaverse/user.cfg``.
3. **Project config** - Per-project settings at ``{project_root}/.dedaverse/project.cfg``.

Use ``LayeredConfig.instance()`` to access the singleton. It loads site and user
config at startup. Project config is loaded on demand via ``current_project`` or
``get_project()``.

Config classes use ``dataclasses_json`` for JSON serialization.
"""

__all__ = [
    'AppConfig',
    'LayeredConfig',
    'PluginConfig',
    'ProjectConfig',
    'ServiceConfig',
    'SiteConfig',
    'UserConfig',
]

import os
import json
import logging
from pathlib import Path

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json


log = logging.getLogger(__name__)


@dataclass_json
@dataclass(eq=False)
class AppConfig:
    """Configuration for a DCC or tool application.

    Attributes:
        name: Application display name.
        version: Version string (e.g. "2024.1").
        command: Executable or command to launch.
        icon_path: Path to application icon.
        install_url: URL for download/installation.
        help_url: URL for documentation or help.
        enabled: Whether the app is enabled for use.
    """

    name: str
    version: str
    command: str
    icon_path: str

    install_url: str
    help_url: str
    enabled: bool

    def __eq__(self, other):
        if not isinstance(other, AppConfig):
            return NotImplemented
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)
    

@dataclass_json
@dataclass(eq=False)
class PluginConfig:
    """Configuration for a Dedaverse plugin.

    Attributes:
        name: Plugin name (e.g. "perforce", "jira").
        version: Plugin version string.
        enabled: Whether the plugin is enabled.
        installed: Whether the plugin is installed.
        url: URL for plugin discovery or installation.
    """

    name: str
    version: str
    enabled: bool
    installed: bool
    url: str

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version 
    
    def __hash__(self):
        return hash((self.name, self.version))    
    

@dataclass_json
@dataclass(eq=False)
class ServiceConfig:
    """Configuration for a REST-based service.

    Services are parameterized APIs (e.g. Perforce, Jira) exposed in the UI.

    Attributes:
        name: Service name (e.g. "perforce", "jira").
        enabled: Whether the service is enabled.
        url: Base URL for the service.
        params: Optional list of parameter names or values.
    """

    name: str
    enabled: bool
    url: str
    params: list[str] = field(default_factory=list)

    def __eq__(self, other):
        # We compare name only because we do not want projects and users 
        # to be able to override the services with their own (ie, Perforce, Jira, etc.)
        return self.name == other.name  
    
    def __hash__(self):
        return hash(self.name)  # ServiceConfig only compares by name, no version field    
    

@dataclass_json
@dataclass
class SiteConfig:
    """Site-wide configuration for all users and projects.

    Loaded from the path in ``DEDAVERSE_SITE_CONFIG`` env var. Used by system
    administrators or pipeline teams to define studio defaults.

    Attributes:
        name: Studio or site name.
        plugin_urls: URLs for plugin discovery and updates, in priority order.
        plugins: List of plugin configurations.
        services: List of service configurations.
        apps: List of application configurations.
        projects: Map of project name to rootdir (predefined projects).
    """

    name: str | None = None
    plugin_urls: list[str] = field(default_factory=list)
    plugins: list[PluginConfig] = field(default_factory=list)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)
    projects: dict[str, str] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.name)

    @classmethod
    def load(cls) -> 'SiteConfig | None':
        """Load site config from DEDAVERSE_SITE_CONFIG path.

        Returns:
            SiteConfig if the env var is set and file exists, else None.
        """
        site_config_path = os.getenv('DEDAVERSE_SITE_CONFIG')
        if not site_config_path:
            return
        site_config_file = Path(site_config_path)
        if site_config_file.is_file():
            with open(site_config_file, 'r') as f:
                data = f.read()
            return cls.from_json(data)
        return cls()

    def save(self) -> None:
        site_config_path = os.getenv('DEDAVERSE_SITE_CONFIG')
        if not site_config_path:
            return
        site_config_file = Path(site_config_path)
        site_config_dir = site_config_file.parent
        try:
            site_config_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        # TODO: check if we can write to the file
        with open(site_config_file, 'w') as f:
            json.dump(self.to_dict(), f, sort_keys=True, indent=4)


@dataclass_json
@dataclass
class ProjectConfig:
    """Project-level configuration for a Dedaverse project.

    Stored at ``{rootdir}/.dedaverse/project.cfg``. Defines project metadata,
    asset types, plugins, services, and apps for the project.

    Attributes:
        name: Project display name.
        rootdir: Project root directory on disk.
        cfg_path: Path to the config file; defaults to
            ``{rootdir}/.dedaverse/project.cfg`` if unset.
        key: Optional short identifier (e.g. "FEN").
        hdr_images_dir: Optional directory path for HDR/environment textures (dome light).
        lights_root: Optional directory path for lights (relative to rootdir or absolute).
        materials_root: Optional directory path for materials (relative to rootdir or absolute).
        project_type: Project type for asset type mapping during creation.
        asset_types: List of asset type names for this project.
        plugins: List of plugin configurations.
        services: List of service names.
        apps: List of application configurations (exposed in Apps panel).
    """

    name: str
    rootdir: str

    cfg_path: str | None = None
    key: str | None = None
    hdr_images_dir: str | None = None
    lights_root: str | None = None
    materials_root: str | None = None

    project_type: str | None = None

    asset_types: list[str] = field(default_factory=list)

    plugins: list[PluginConfig] = field(default_factory=list)

    services: list[str] = field(default_factory=list)

    apps: list[AppConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        """When apps list is empty (new studio config), add the default Dedaverse viewer app."""
        if not self.apps:
            self.apps.append(AppConfig(
                name='Dedaverse',
                version='',
                command='python -m deda.core.viewer',
                icon_path='',
                install_url='',
                help_url='',
                enabled=True,
            ))
    
    def __eq__(self, other):
        return self.name == str(other) 
    
    def __hash__(self):
        return hash(self.name)  
    
    def __str__(self):
        return self.name
    
    @property
    def is_writable(self) -> bool:
        """True if the project config file can be written."""
        if not self.cfg_path:
            return True
        if not Path(self.cfg_path).is_file():
            return True
        return os.access(self.cfg_path, os.W_OK)
    
    @classmethod
    def load(cls, path: str | Path) -> 'ProjectConfig | None':
        """Load project config from a path.

        Args:
            path: Path to project root dir or to project.cfg. If a directory,
                looks for ``.dedaverse/project.cfg`` inside.

        Returns:
            ProjectConfig if file exists, else None.
        """
        if not path:
            log.error('Project must have a config path to load from.')
            return
        path_obj = Path(path)
        if path_obj.is_dir():
            path_obj = path_obj / '.dedaverse' / 'project.cfg'
        path_str = path_obj.as_posix()
        if not path_obj.is_file():
            log.warning(f'Project config does not exist. {path_str}')
            return
        with open(path_obj, 'r') as f:
            data = f.read()
        project = cls.from_json(data)
        # Ensure future saves will go to the same file on disk.
        project.cfg_path = path_str
        return project

    def save(self) -> None:
        if not self.is_writable:
            return
        if not self.cfg_path:
            if not self.rootdir:
                log.error('Cannot save the project config file because neither rootdir or cfg_path are set for the project.')
                return
            cfg_path_obj = Path(self.rootdir) / '.dedaverse' / 'project.cfg'
            self.cfg_path = cfg_path_obj.as_posix()
        project_config_path = Path(self.cfg_path)
        project_config_dir = project_config_path.parent
        try:
            project_config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            if 'already exists' not in str(err):
                log.error(err)
        # TODO: check if we can write to the file (ie, p4 managed file, or system permissions)
        with open(self.cfg_path, 'w') as f:
            #f.write(self.to_json())    
            json.dump(self.to_dict(), f, sort_keys=True, indent=4)
    
    
@dataclass_json
@dataclass
class UserConfig:
    """Per-user configuration stored at ``~/.dedaverse/user.cfg``.

    Attributes:
        current_project: Name of the currently active project.
        projects: Map of project name to rootdir (or ProjectConfig when loaded).
        roles: User roles (e.g. animator, rigger, concept artist).
        plugins: List of plugin configurations.
        services: List of service configurations.
        apps: List of application configurations.
    """

    current_project: str | None = None
    projects: dict[str, str] = field(default_factory=dict)
    roles: list[str] = field(default_factory=list)

    plugins: list[PluginConfig] = field(default_factory=list)
    services: list[ServiceConfig] = field(default_factory=list)
    apps: list[AppConfig] = field(default_factory=list)

    @classmethod
    def load(cls) -> 'UserConfig':
        """Load user config from ~/.dedaverse/user.cfg.

        Returns:
            UserConfig. Creates empty config if file does not exist.
        """
        user_config_path = Path.home() / '.dedaverse' / 'user.cfg'
        if user_config_path.is_file():
            with open(user_config_path, 'r') as f:
                data = f.read()
            return cls.from_json(data)            
        return cls()
    
    def add_project(self, project: ProjectConfig) -> None:
        """Add a project to the user's project list.

        Args:
            project: ProjectConfig to add.

        Raises:
            TypeError: If project is not a ProjectConfig.
        """
        if not isinstance(project, ProjectConfig):
            raise TypeError('Project must be a valid ProjectConfig!')
        self.projects[project.name] = project
        
    def load_project(self, proj_name: str) -> None:
        """Load the ProjectConfig for the given project from disk.

        Replaces the rootdir entry in projects with the loaded ProjectConfig.

        Args:
            proj_name: Name of the project to load.

        Raises:
            ValueError: If proj_name is not in the project list.
        """
        if proj_name not in self.projects:
            raise ValueError(f'Cannot load project {proj_name}!')
        if isinstance(self.projects[proj_name], ProjectConfig):
            return # already loaded
        rootdir = self.projects[proj_name]
        self.projects[proj_name] = ProjectConfig.load(rootdir)
        # check for proj name change that may have been changed elsewhere
        if self.projects[proj_name].name != proj_name:
            self.projects[self.projects[proj_name].name] = self.projects[proj_name]
            del self.projects[proj_name]
            if self.current_project == proj_name:
                self.current_proj = self.projects[proj_name].name
    
    def save(self) -> None:
        """Persist user config to ~/.dedaverse/user.cfg."""
        user_config_path = Path.home() / '.dedaverse' / 'user.cfg'
        user_config_dir = user_config_path.parent
        try:
            user_config_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        with open(user_config_path, 'w') as f:
            #f.write(self.to_json())
            data = self.to_dict()
            proj_map = dict()
            for name, project in data['projects'].items():
                if isinstance(project, str):
                    proj_map[name] = project
                elif isinstance(project, ProjectConfig):
                    proj_map[name] = project.rootdir
                else:
                    proj_map[name] = project['rootdir']
            data['projects'] = proj_map
            json.dump(data, f, sort_keys=True, indent=4)
    

class LayeredConfig:
    """Singleton providing merged site, user, and project configuration.

    Use ``LayeredConfig.instance()`` to get the singleton. On first access,
    site and user config are loaded. Project config is loaded on demand when
    ``current_project`` or ``projects`` is accessed.
    """

    # Default studio app when no site config file is loaded (so Dedaverse viewer is always available)
    _DEFAULT_STUDIO_APP = AppConfig(
        name='Dedaverse',
        version='',
        command='python -m deda.core.viewer',
        icon_path='',
        install_url='',
        help_url='',
        enabled=True,
    )

    def __init__(self):
        
        self._all_projects = {}
        
        # The site config is loaded to include the settings for all users and all projects
        # This is retrieved via env var, and set up by system administrators or pipeline teams
        self._site_config = SiteConfig.load()
        # When no site config exists or it has no apps, ensure studio layer has Dedaverse so it is inherited
        if self._site_config is None:
            self._site_config = SiteConfig(
                name=None,
                plugin_urls=[],
                plugins=[],
                services=[],
                apps=[self._DEFAULT_STUDIO_APP],
                projects={},
            )
        elif not self._site_config.apps:
            self._site_config.apps = [self._DEFAULT_STUDIO_APP]
               
        # Loaded first, when the system starts. If not found, opens up a <new project>
        self._user_config = UserConfig.load()
        
    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        return cls._instance 
    
    @classmethod
    def instance(cls) -> 'LayeredConfig':
        """Return the LayeredConfig singleton."""
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        return cls._instance
               
    @property
    def user(self) -> UserConfig:
        """The user configuration."""
        return self._user_config

    @property
    def site(self) -> 'SiteConfig | None':
        """The site (studio) configuration, if loaded."""
        return self._site_config

    def get_merged_apps(self) -> list[AppConfig]:
        """Return apps from site, user, and current project layers.
        Later layers override earlier when the same app name exists.
        Order: site first, then user, then project.
        """
        merged: list[AppConfig] = []
        by_name: dict[str, int] = {}
        site_apps = (self._site_config.apps if self._site_config else []) or []
        user_apps = self.user.apps or []
        project_apps = (self.current_project.apps if self.current_project else []) or []
        for app in site_apps + user_apps + project_apps:
            if app.name in by_name:
                merged[by_name[app.name]] = app
            else:
                by_name[app.name] = len(merged)
                merged.append(app)
        return merged

    @property
    def current_project(self) -> ProjectConfig | None:
        if not self.user.projects or not self.user.current_project:
            return
        project = self.user.projects[self.user.current_project]
        if not isinstance(project, ProjectConfig):
            # Cache the loaded project config from the cfg file in the rootdir
            data = ProjectConfig.load(project)
            if not data:
                data = ProjectConfig(name=self.user.current_project, rootdir=project)
            assert data
            if data:
                self.user.projects[self.user.current_project] = data
        return self.user.projects[self.user.current_project]
    
    @current_project.setter
    def current_project(self, project: ProjectConfig) -> None:
        if not isinstance(project, ProjectConfig):
            raise TypeError('Current project must be a ProjectConfig type!')
        #if project not in self.projects:
        #    raise ValueError(f'Project {project} is not in the user config list of available projects!')
        if project not in self.user.projects:
            # we should only get here if the project is not defined at the site level
            self.user.add_project(project)        
        self.user.current_project = str(project) 
        
    @property
    def projects(self):
        """Iterate over all projects (loaded on demand)."""
        data = dict(self.user.projects)
        for project_name, project in data.items():
            if isinstance(project, str):
                proj = ProjectConfig.load(project)
                if not proj:
                    proj = ProjectConfig(name=project_name, rootdir=project)
                self.user.projects[project_name] = proj
                project = proj
            yield project
            
    def get_project(self, name: str) -> ProjectConfig | None:
        """Return the ProjectConfig for the given project name."""
        for project in self.projects:
            if project.name == name:
                return project
            
    def save(self) -> None:
        """Persist user and site config to disk."""
        self._user_config.save()
        if self._site_config:
            self._site_config.save()
        