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
"""Unit tests for deda.core._plugin module."""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock, Mock

from deda.core._plugin import (
    Plugin,
    PluginRegistry,
    Application,
    FileManager,
    NotificationSystem,
    Service,
    TaskManager,
    Tool,
    initialize_plugins,
)


class TestPlugin(unittest.TestCase):
    """Test cases for Plugin base class."""

    def test_plugin_creation(self):
        """Test creating a Plugin instance."""
        plugin = Plugin(
            name='TestPlugin',
            version='1.0.0',
            vendor='TestVendor',
            description='Test description',
            image='/path/to/image.png',
        )
        self.assertEqual(plugin.name, 'TestPlugin')
        self.assertIsNotNone(plugin.version)
        self.assertEqual(plugin.vendor, 'TestVendor')
        self.assertEqual(plugin.description, 'Test description')
        self.assertEqual(plugin.image, '/path/to/image.png')
        self.assertFalse(plugin.loaded)

    def test_plugin_load_not_implemented(self):
        """Test that Plugin.load() raises NotImplementedError."""
        plugin = Plugin(name='TestPlugin')
        with self.assertRaises(NotImplementedError):
            plugin.load()


class TestPluginRegistry(unittest.TestCase):
    """Test cases for PluginRegistry."""

    def setUp(self):
        """Set up test fixtures."""
        PluginRegistry._registry_.clear()

    def test_plugin_registry_register(self):
        """Test registering a plugin."""
        registry = PluginRegistry()
        plugin = Plugin(name='TestPlugin')
        registry.register(plugin)
        self.assertIn('TestPlugin', PluginRegistry._registry_)

    def test_plugin_registry_get(self):
        """Test getting a plugin from registry."""
        registry = PluginRegistry()
        plugin = Plugin(name='TestPlugin')
        registry.register(plugin)
        retrieved = registry.get('TestPlugin')
        self.assertEqual(retrieved, plugin)
        self.assertIsNone(registry.get('NonexistentPlugin'))

    def test_plugin_registry_iter(self):
        """Test iterating over plugins in registry."""
        registry = PluginRegistry()
        plugin1 = Plugin(name='Plugin1')
        plugin2 = Plugin(name='Plugin2')
        registry.register(plugin1)
        registry.register(plugin2)
        plugins = list(registry)
        self.assertEqual(len(plugins), 2)
        self.assertIn(plugin1, plugins)
        self.assertIn(plugin2, plugins)

    def test_plugin_registry_iter_plugins(self):
        """Test iterating over plugins of specific type."""
        registry = PluginRegistry()
        app_plugin = Application(app_name='AppPlugin', executable='app.exe')
        file_plugin = FileManager(name='FilePlugin')
        registry.register(app_plugin)
        registry.register(file_plugin)
        
        apps = list(registry.iter_plugins(Application))
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0], app_plugin)


class TestApplication(unittest.TestCase):
    """Test cases for Application plugin."""

    def test_application_creation(self):
        """Test creating an Application instance."""
        app = Application(
            app_name='TestApp',
            executable='/path/to/app.exe',
        )
        self.assertEqual(app.name, 'TestApp')
        self.assertEqual(app._executable, '/path/to/app.exe')

    def test_application_set_executable(self):
        """Test setting executable path."""
        app = Application(app_name='TestApp')
        app.set_executable('/path/to/app.exe')
        self.assertEqual(app._executable, '/path/to/app.exe')

    def test_application_set_executable_invalid_type(self):
        """Test setting invalid executable type raises TypeError."""
        app = Application(app_name='TestApp')
        with self.assertRaises(TypeError):
            app.set_executable(123)

    def test_application_find_not_implemented(self):
        """Test that Application.find() raises NotImplementedError."""
        app = Application(app_name='TestApp')
        with self.assertRaises(NotImplementedError):
            app.find()

    def test_application_setup_env(self):
        """Test setup_env returns env dict."""
        app = Application(app_name='TestApp')
        env = {'TEST': 'value'}
        result = app.setup_env(env)
        self.assertEqual(result, env)

    @patch('deda.core._plugin.subprocess.run')
    @patch('deda.core._plugin.os.environ.copy')
    def test_application_launch(self, mock_env_copy, mock_subprocess):
        """Test launching an application."""
        mock_env_copy.return_value = {'TEST': 'value'}
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        app = Application(app_name='TestApp', executable='/path/to/app.exe')
        result = app.launch('arg1', 'arg2', key='value')
        
        mock_subprocess.assert_called_once()
        self.assertIsNotNone(result)


class TestFileManager(unittest.TestCase):
    """Test cases for FileManager plugin."""

    def test_file_manager_creation(self):
        """Test creating a FileManager instance."""
        fm = FileManager(name='TestFileManager')
        self.assertEqual(fm.name, 'TestFileManager')

    def test_file_manager_can_handle_not_implemented(self):
        """Test that can_handle() raises NotImplementedError."""
        fm = FileManager(name='TestFileManager')
        with self.assertRaises(NotImplementedError):
            fm.can_handle(['file.txt'])

    def test_file_manager_add_not_implemented(self):
        """Test that add() raises NotImplementedError."""
        fm = FileManager(name='TestFileManager')
        with self.assertRaises(NotImplementedError):
            fm.add(['file.txt'])


class TestNotificationSystem(unittest.TestCase):
    """Test cases for NotificationSystem plugin."""

    def test_notification_system_creation(self):
        """Test creating a NotificationSystem instance."""
        ns = NotificationSystem(name='TestNotification')
        self.assertEqual(ns.name, 'TestNotification')

    def test_notification_system_notify_not_implemented(self):
        """Test that notify() raises NotImplementedError."""
        ns = NotificationSystem(name='TestNotification')
        with self.assertRaises(NotImplementedError):
            ns.notify('Title', 'Message')


class TestService(unittest.TestCase):
    """Test cases for Service plugin."""

    def test_service_creation(self):
        """Test creating a Service instance."""
        service = Service(name='TestService', url='https://example.com')
        self.assertEqual(service.name, 'TestService')


class TestTaskManager(unittest.TestCase):
    """Test cases for TaskManager plugin."""

    def test_task_manager_creation(self):
        """Test creating a TaskManager instance."""
        tm = TaskManager(name='TestTaskManager')
        self.assertEqual(tm.name, 'TestTaskManager')

    def test_task_manager_get_task_not_implemented(self):
        """Test that get_task() raises NotImplementedError."""
        tm = TaskManager(name='TestTaskManager')
        with self.assertRaises(NotImplementedError):
            tm.get_task({})

    def test_task_manager_update_task_not_implemented(self):
        """Test that update_task() raises NotImplementedError."""
        tm = TaskManager(name='TestTaskManager')
        with self.assertRaises(NotImplementedError):
            tm.update_task({})


class TestTool(unittest.TestCase):
    """Test cases for Tool plugin."""

    def test_tool_creation(self):
        """Test creating a Tool instance."""
        tool = Tool(name='TestTool')
        self.assertEqual(tool.name, 'TestTool')
        self.assertIsNone(tool._window_instance)

    def test_tool_initialize_window_not_implemented(self):
        """Test that initialize_window() raises NotImplementedError."""
        tool = Tool(name='TestTool')
        with self.assertRaises(NotImplementedError):
            tool.initialize_window(None)


class TestInitializePlugins(unittest.TestCase):
    """Test cases for initialize_plugins function."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('deda.core._plugin.pkgutil.walk_packages')
    @patch('deda.core._plugin.sys.modules')
    def test_initialize_plugins_no_env(self, mock_modules, mock_walk):
        """Test initializing plugins when DEDAVERSE_PLUGIN_DIRS is not set."""
        mock_walk.return_value = []
        initialize_plugins()
        mock_walk.assert_called_once()

    @patch.dict(os.environ, {'DEDAVERSE_PLUGIN_DIRS': '/path1:/path2'})
    @patch('deda.core._plugin.pkgutil.walk_packages')
    def test_initialize_plugins_with_env(self, mock_walk):
        """Test initializing plugins with DEDAVERSE_PLUGIN_DIRS set."""
        mock_walk.return_value = []
        initialize_plugins()
        mock_walk.assert_called_once()


if __name__ == '__main__':
    unittest.main()
