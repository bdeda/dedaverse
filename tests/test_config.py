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
"""Unit tests for deda.core._config module."""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from deda.core._config import (
    AppConfig,
    PluginConfig,
    ServiceConfig,
    SiteConfig,
    ProjectConfig,
    UserConfig,
    LayeredConfig,
)


class TestAppConfig(unittest.TestCase):
    """Test cases for AppConfig."""

    def test_app_config_creation(self):
        """Test creating an AppConfig instance."""
        app = AppConfig(
            name='TestApp',
            version='1.0.0',
            command='testapp',
            icon_path='/path/to/icon.png',
            install_url='https://example.com',
            help_url='https://example.com/help',
            enabled=True,
        )
        self.assertEqual(app.name, 'TestApp')
        self.assertEqual(app.version, '1.0.0')
        self.assertEqual(app.command, 'testapp')
        self.assertTrue(app.enabled)

    def test_app_config_equality(self):
        """Test AppConfig equality comparison."""
        app1 = AppConfig(
            name='TestApp', version='1.0.0', command='test', icon_path='', 
            install_url='', help_url='', enabled=True
        )
        app2 = AppConfig(
            name='TestApp', version='1.0.0', command='test', icon_path='', 
            install_url='', help_url='', enabled=True
        )
        app3 = AppConfig(
            name='TestApp', version='2.0.0', command='test', icon_path='', 
            install_url='', help_url='', enabled=True
        )
        self.assertEqual(app1, app2)
        self.assertNotEqual(app1, app3)

    def test_app_config_hash(self):
        """Test AppConfig hashing."""
        app1 = AppConfig(
            name='TestApp', version='1.0.0', command='test', icon_path='', 
            install_url='', help_url='', enabled=True
        )
        app2 = AppConfig(
            name='TestApp', version='1.0.0', command='test', icon_path='', 
            install_url='', help_url='', enabled=True
        )
        self.assertEqual(hash(app1), hash(app2))


class TestPluginConfig(unittest.TestCase):
    """Test cases for PluginConfig."""

    def test_plugin_config_creation(self):
        """Test creating a PluginConfig instance."""
        plugin = PluginConfig(
            name='TestPlugin',
            version='1.0.0',
            enabled=True,
            installed=True,
            url='https://example.com',
        )
        self.assertEqual(plugin.name, 'TestPlugin')
        self.assertEqual(plugin.version, '1.0.0')
        self.assertTrue(plugin.enabled)
        self.assertTrue(plugin.installed)

    def test_plugin_config_equality(self):
        """Test PluginConfig equality comparison."""
        plugin1 = PluginConfig(
            name='TestPlugin', version='1.0.0', enabled=True, 
            installed=True, url=''
        )
        plugin2 = PluginConfig(
            name='TestPlugin', version='1.0.0', enabled=True, 
            installed=True, url=''
        )
        plugin3 = PluginConfig(
            name='TestPlugin', version='2.0.0', enabled=True, 
            installed=True, url=''
        )
        self.assertEqual(plugin1, plugin2)
        self.assertNotEqual(plugin1, plugin3)


class TestServiceConfig(unittest.TestCase):
    """Test cases for ServiceConfig."""

    def test_service_config_creation(self):
        """Test creating a ServiceConfig instance."""
        service = ServiceConfig(
            name='TestService',
            enabled=True,
            url='https://example.com',
            params=['param1', 'param2'],
        )
        self.assertEqual(service.name, 'TestService')
        self.assertTrue(service.enabled)
        self.assertEqual(len(service.params), 2)

    def test_service_config_equality(self):
        """Test ServiceConfig equality comparison (by name only)."""
        service1 = ServiceConfig(name='TestService', enabled=True, url='')
        service2 = ServiceConfig(name='TestService', enabled=False, url='')
        service3 = ServiceConfig(name='OtherService', enabled=True, url='')
        self.assertEqual(service1, service2)  # Same name
        self.assertNotEqual(service1, service3)  # Different name


class TestSiteConfig(unittest.TestCase):
    """Test cases for SiteConfig."""

    def test_site_config_creation(self):
        """Test creating a SiteConfig instance."""
        site = SiteConfig(name='TestSite')
        self.assertEqual(site.name, 'TestSite')
        self.assertEqual(len(site.plugins), 0)
        self.assertEqual(len(site.services), 0)
        self.assertEqual(len(site.apps), 0)

    @patch.dict(os.environ, {}, clear=True)
    def test_site_config_load_no_env(self):
        """Test loading SiteConfig when env var is not set."""
        site = SiteConfig.load()
        self.assertIsNone(site)

    @patch.dict(os.environ, {'DEDAVERSE_SITE_CONFIG': '/nonexistent/path.cfg'})
    def test_site_config_load_nonexistent(self):
        """Test loading SiteConfig when file doesn't exist."""
        site = SiteConfig.load()
        self.assertIsNone(site)

    def test_site_config_save_no_env(self):
        """Test saving SiteConfig when env var is not set."""
        site = SiteConfig(name='TestSite')
        result = site.save()
        self.assertIsNone(result)


class TestProjectConfig(unittest.TestCase):
    """Test cases for ProjectConfig."""

    def test_project_config_creation(self):
        """Test creating a ProjectConfig instance."""
        project = ProjectConfig(
            name='TestProject',
            rootdir='/path/to/project',
        )
        self.assertEqual(project.name, 'TestProject')
        self.assertEqual(project.rootdir, '/path/to/project')
        self.assertTrue(project.is_writable)

    def test_project_config_str(self):
        """Test ProjectConfig string representation."""
        project = ProjectConfig(name='TestProject', rootdir='/path')
        self.assertEqual(str(project), 'TestProject')

    def test_project_config_equality(self):
        """Test ProjectConfig equality comparison."""
        project1 = ProjectConfig(name='TestProject', rootdir='/path1')
        project2 = ProjectConfig(name='TestProject', rootdir='/path2')
        self.assertEqual(project1, project2)  # Compared by name
        self.assertEqual(project1, 'TestProject')  # Can compare with string

    def test_project_config_is_writable(self):
        """Test ProjectConfig is_writable property."""
        project = ProjectConfig(name='TestProject', rootdir='/path')
        self.assertTrue(project.is_writable)
        
        project.cfg_path = '/nonexistent/path.cfg'
        self.assertTrue(project.is_writable)  # File doesn't exist, so writable

    def test_project_config_load_nonexistent(self):
        """Test loading ProjectConfig from nonexistent path."""
        result = ProjectConfig.load('/nonexistent/path')
        self.assertIsNone(result)

    def test_project_config_load_from_dir(self):
        """Test loading ProjectConfig from directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_dir = os.path.join(tmpdir, '.dedaverse')
            os.makedirs(cfg_dir)
            cfg_path = os.path.join(cfg_dir, 'project.cfg')
            
            project_data = {
                'name': 'TestProject',
                'rootdir': tmpdir,
            }
            import json
            with open(cfg_path, 'w') as f:
                json.dump(project_data, f)
            
            project = ProjectConfig.load(tmpdir)
            self.assertIsNotNone(project)
            self.assertEqual(project.name, 'TestProject')
            self.assertEqual(project.cfg_path.replace('\\', '/'), cfg_path.replace('\\', '/'))


class TestUserConfig(unittest.TestCase):
    """Test cases for UserConfig."""

    def test_user_config_creation(self):
        """Test creating a UserConfig instance."""
        user = UserConfig()
        self.assertIsNone(user.current_project)
        self.assertEqual(len(user.projects), 0)
        self.assertEqual(len(user.roles), 0)

    def test_user_config_add_project(self):
        """Test adding a project to UserConfig."""
        user = UserConfig()
        project = ProjectConfig(name='TestProject', rootdir='/path')
        user.add_project(project)
        self.assertIn('TestProject', user.projects)
        self.assertEqual(user.projects['TestProject'], project)

    def test_user_config_add_project_invalid_type(self):
        """Test adding invalid project type raises TypeError."""
        user = UserConfig()
        with self.assertRaises(TypeError):
            user.add_project('not a project')


class TestLayeredConfig(unittest.TestCase):
    """Test cases for LayeredConfig."""

    def test_layered_config_singleton(self):
        """Test that LayeredConfig is a singleton."""
        cfg1 = LayeredConfig()
        cfg2 = LayeredConfig.instance()
        cfg3 = LayeredConfig()
        self.assertIs(cfg1, cfg2)
        self.assertIs(cfg1, cfg3)

    def test_layered_config_user_property(self):
        """Test accessing user config property."""
        cfg = LayeredConfig()
        user = cfg.user
        self.assertIsInstance(user, UserConfig)

    def test_layered_config_current_project_setter(self):
        """Test setting current project."""
        cfg = LayeredConfig()
        project = ProjectConfig(name='TestProject', rootdir='/path')
        cfg.current_project = project
        self.assertEqual(cfg.user.current_project, 'TestProject')

    def test_layered_config_current_project_setter_invalid_type(self):
        """Test setting invalid project type raises TypeError."""
        cfg = LayeredConfig()
        with self.assertRaises(TypeError):
            cfg.current_project = 'not a project'


if __name__ == '__main__':
    unittest.main()
