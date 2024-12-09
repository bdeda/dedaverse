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
__all__ = ['check_for_updates', 'get_latest_release_name']

import os
import logging
import requests
from packaging.version import Version


log = logging.getLogger(__name__)


def get_latest_release_name(owner, repo):
    """Check if dataverse has had any new releases in the github repository, 
    and notify the user if there are updates available.
    
    Uses the DEDAVERSE_GITUB_API_ROOT_URL env var to check for an updated release.
    This can be mapped to an internal github enterprise server where internal 
    Pipeline teams are managing the releases for their team.
    
    """
    github_api_root_url = os.getenv('DEDAVERSE_GITUB_API_ROOT_URL', 'http://api.github.com')
    url = f'{github_api_root_url}/repos/{owner}/{repo}/releases/latest'
    response = requests.get(url)
    data = response.json()
    log.debug(data)
    if data.get('status') == '404':
        log.error(data)
    version = data.get('tag_name')
    if not version:    
        version = data.get("name", '0.1.0')
    if version.startswith('v'):
        version = version[1:]
    return Version(version)


def check_for_updates():
    """Check if dataverse has had any new releases in the github repository, 
    and notify the user if there are updates available.
    
    Returns:
        (bool) True if there are updates available, otherwise False.
    
    """
    import deda
    latest_version = get_latest_release_name('bdeda', 'dedaverse')
    log.info(f'Latest release is {latest_version}')
    current_version = Version(deda.__version__)
    log.info(f'Current version is {current_version}')
    if latest_version > current_version:
        return True
    
    # TODO: check for plugin updates in their repos.
    # example on how to check a github repo for updated release
    usd_version = get_latest_release_name('PixarAnimationStudios', 'OpenUSD')
    log.info(f'Usd version available: {usd_version}')
    
    
if __name__ == '__main__':
    import deda.log
    deda.log.initialize(logging.DEBUG)
    check_for_updates()
    