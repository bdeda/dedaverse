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
"""Unit tests for dedaverse.__main__ module."""

import unittest
import os
import sys
import platform
from unittest.mock import patch, MagicMock

try:
    import click
    from click.testing import CliRunner
    import dedaverse.__main__
    MODULE_AVAILABLE = True
    CLICK_AVAILABLE = True
except ImportError:
    MODULE_AVAILABLE = False
    CLICK_AVAILABLE = False


@unittest.skipIf(not MODULE_AVAILABLE, "__main__ module not available")
class TestDedaverseMain(unittest.TestCase):
    """Test cases for dedaverse.__main__ module."""

    def setUp(self):
        """Set up test fixtures."""
        if CLICK_AVAILABLE:
            self.runner = CliRunner()

    def test_dedaverse_group_exists(self):
        """Test that dedaverse click group exists."""
        from dedaverse.__main__ import dedaverse
        self.assertIsNotNone(dedaverse)

    @patch('dedaverse.__main__.deda.app.run')
    def test_run_command(self, mock_run):
        """Test the run command."""
        from dedaverse.__main__ import dedaverse
        mock_run.return_value = 0
        
        # Use CliRunner to properly invoke the Click command
        result = self.runner.invoke(dedaverse, ['run'])
        self.assertEqual(result.exit_code, 0)
        mock_run.assert_called_once()

    @patch('dedaverse.__main__.os.path.isfile')
    @patch('dedaverse.__main__.open', create=True)
    @patch('dedaverse.__main__.getpass.getuser')
    @patch('dedaverse.__main__.platform.system')
    def test_install_command_windows(self, mock_platform, mock_getuser, mock_open, mock_isfile):
        """Test the install command on Windows."""
        from dedaverse.__main__ import dedaverse
        
        mock_platform.return_value = 'Windows'
        mock_getuser.return_value = 'testuser'
        mock_isfile.return_value = True
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Use CliRunner to properly invoke the Click command
        result = self.runner.invoke(dedaverse, ['install'])
        self.assertEqual(result.exit_code, 0)
        mock_open.assert_called_once()

    @patch('dedaverse.__main__.platform.system')
    def test_install_command_non_windows(self, mock_platform_system):
        """Test the install command on non-Windows systems."""
        mock_platform_system.return_value = 'Linux'
        
        from dedaverse.__main__ import dedaverse
        
        # Use CliRunner to properly invoke the Click command
        result = self.runner.invoke(dedaverse, ['install'])
        # Should return 1 (not implemented) on non-Windows
        # Click commands return the function's return value as exit_code
        # If exit_code is 0, check if it's because the function returned 0 or an exception occurred
        if result.exit_code != 1:
            # Debug: check what actually happened
            print(f"DEBUG: exit_code={result.exit_code}, output={result.output}, exception={result.exception}")
        
        self.assertEqual(result.exit_code, 1, 
                        f"Expected exit_code 1, got {result.exit_code}. Output: {result.output}")
        # Also verify the output message indicates it's not implemented
        self.assertIn('not yet implemented', result.output.lower() or '')


if __name__ == '__main__':
    unittest.main()
