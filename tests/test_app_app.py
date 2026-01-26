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
"""Unit tests for deda.app._app module."""

import unittest
import platform
from unittest.mock import patch, MagicMock
from PySide6 import QtWidgets


class TestApplication(unittest.TestCase):
    """Test cases for Application class."""

    def setUp(self):
        """Ensure no QApplication instance exists before each test."""
        app = QtWidgets.QApplication.instance()
        if app is not None:
            # Can't easily destroy QApplication singleton, so we'll skip these tests
            # if an instance already exists
            pass

    @patch('deda.app._app.platform.system')
    def test_application_creation_windows(self, mock_platform):
        """Test creating an Application instance on Windows."""
        # Skip if QApplication instance already exists (singleton behavior)
        if QtWidgets.QApplication.instance() is not None:
            self.skipTest("QApplication instance already exists - cannot test Application creation")
        
        mock_platform.return_value = 'Windows'
        from deda.app._app import Application
        app = Application()
        self.assertIsInstance(app, QtWidgets.QApplication)
        # Clean up
        app.quit()

    @patch('deda.app._app.platform.system')
    def test_application_creation_linux(self, mock_platform):
        """Test creating an Application instance on Linux."""
        # Skip if QApplication instance already exists (singleton behavior)
        if QtWidgets.QApplication.instance() is not None:
            self.skipTest("QApplication instance already exists - cannot test Application creation")
        
        mock_platform.return_value = 'Linux'
        from deda.app._app import Application
        app = Application()
        self.assertIsInstance(app, QtWidgets.QApplication)
        # Clean up
        app.quit()


class TestRun(unittest.TestCase):
    """Test cases for run function."""

    @patch('deda.app._app.deda.log.initialize')
    @patch('deda.app._app.deda.core.initialize')
    @patch('deda.app._app.Application')
    @patch('deda.app._app.MainWindow')
    @patch('deda.app._app.deda.core.PluginRegistry')
    def test_run_function(self, mock_registry, mock_main_window, mock_app_class, 
                          mock_core_init, mock_log_init):
        """Test the run function."""
        from deda.app._app import run
        
        mock_app_instance = MagicMock()
        mock_app_instance.exec_.return_value = 0
        mock_app_class.return_value = mock_app_instance
        
        mock_registry_instance = MagicMock()
        mock_registry_instance.__iter__ = lambda self: iter([])
        mock_registry.return_value = mock_registry_instance
        
        result = run()
        self.assertEqual(result, 0)
        mock_log_init.assert_called_once()
        mock_core_init.assert_called_once()


if __name__ == '__main__':
    unittest.main()
