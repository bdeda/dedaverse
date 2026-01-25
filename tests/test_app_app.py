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

try:
    from PySide6 import QtWidgets
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False


@unittest.skipIf(not PYSIDE6_AVAILABLE, "PySide6 not available")
class TestApplication(unittest.TestCase):
    """Test cases for Application class."""

    @patch('deda.app._app.ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID')
    def test_application_creation(self, mock_set_app_id):
        """Test creating an Application instance.
        
        This test mocks the Windows-specific ctypes.windll.shell32 call to prevent
        failures on non-Windows systems or in restricted environments.
        """
        from deda.app._app import Application
        app = Application()
        self.assertIsInstance(app, QtWidgets.QApplication)
        
        # Verify Windows-specific call was made only on Windows
        # On non-Windows, the call should not be made due to platform guard
        if platform.system() == 'Windows':
            mock_set_app_id.assert_called_once_with(u'dedafx.dedaverse.0.1.0')
        else:
            # On non-Windows, the call should not be made
            mock_set_app_id.assert_not_called()


@unittest.skipIf(not PYSIDE6_AVAILABLE, "PySide6 not available")
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
