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
"""Unit tests for deda.app._app.get_proc_under_mouse function."""

import unittest
import platform
from unittest.mock import patch, MagicMock

from deda.app._app import get_proc_under_mouse


class TestGetProcUnderMouse(unittest.TestCase):
    """Test cases for get_proc_under_mouse function."""

    def test_get_proc_under_mouse_non_windows(self):
        """Test that get_proc_under_mouse returns None on non-Windows systems."""
        if platform.system() != 'Windows':
            result = get_proc_under_mouse()
            self.assertIsNone(result)

    @unittest.skipIf(platform.system() != 'Windows', "Windows-specific test")
    @patch('deda.app._app.win32gui.WindowFromPoint')
    @patch('deda.app._app.win32gui.GetCursorPos')
    @patch('deda.app._app.win32process.GetWindowThreadProcessId')
    @patch('deda.app._app.psutil.Process')
    def test_get_proc_under_mouse_windows(self, mock_process, mock_get_pid, 
                                          mock_get_cursor, mock_window_from_point):
        """Test get_proc_under_mouse on Windows."""
        mock_get_cursor.return_value = (100, 200)
        mock_window_from_point.return_value = MagicMock()
        mock_get_pid.return_value = (None, 1234)
        mock_process_instance = MagicMock()
        mock_process.return_value = mock_process_instance
        
        result = get_proc_under_mouse()
        self.assertEqual(result, mock_process_instance)
        mock_get_cursor.assert_called_once()
        mock_window_from_point.assert_called_once_with((100, 200))
        mock_get_pid.assert_called_once()
        mock_process.assert_called_once_with(1234)


if __name__ == '__main__':
    unittest.main()
