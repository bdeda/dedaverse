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
"""Unit tests for deda.core._check_for_updates module."""

import unittest
import os
from unittest.mock import patch, MagicMock

from deda.core._check_for_updates import get_latest_release_name


class TestCheckForUpdates(unittest.TestCase):
    """Test cases for check_for_updates module."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('deda.core._check_for_updates.requests.get')
    def test_get_latest_release_name_success(self, mock_get):
        """Test getting latest release name successfully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'tag_name': 'v1.2.3'}
        mock_get.return_value = mock_response
        
        result = get_latest_release_name('owner', 'repo')
        self.assertIsNotNone(result)
        mock_get.assert_called_once()

    @patch.dict(os.environ, {'DEDAVERSE_GITUB_API_ROOT_URL': 'https://custom.github.com'})
    @patch('deda.core._check_for_updates.requests.get')
    def test_get_latest_release_name_custom_url(self, mock_get):
        """Test getting latest release with custom GitHub URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'tag_name': 'v1.2.3'}
        mock_get.return_value = mock_response
        
        get_latest_release_name('owner', 'repo')
        call_url = mock_get.call_args[0][0]
        self.assertIn('custom.github.com', call_url)

    @patch('deda.core._check_for_updates.requests.get')
    def test_get_latest_release_name_no_tag(self, mock_get):
        """Test getting latest release when tag_name is missing."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'name': '1.2.3'}
        mock_get.return_value = mock_response
        
        result = get_latest_release_name('owner', 'repo')
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
