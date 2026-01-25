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
"""Unit tests for deda.log module."""

import unittest
import logging
from unittest.mock import patch, MagicMock

from deda.log import initialize


class TestLogInitialize(unittest.TestCase):
    """Test cases for initialize function."""

    @patch('deda.log.coloredlogs.install')
    @patch('deda.log.logging.getLogger')
    def test_initialize_default_level(self, mock_get_logger, mock_install):
        """Test initialize with default log level."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        initialize()
        
        mock_get_logger.assert_called_once_with('')
        mock_install.assert_called_once_with(level=logging.DEBUG, logger=mock_logger)

    @patch('deda.log.coloredlogs.install')
    @patch('deda.log.logging.getLogger')
    def test_initialize_custom_level(self, mock_get_logger, mock_install):
        """Test initialize with custom log level."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        initialize(loglevel=logging.INFO)
        
        mock_get_logger.assert_called_once_with('')
        mock_install.assert_called_once_with(level=logging.INFO, logger=mock_logger)


if __name__ == '__main__':
    unittest.main()
