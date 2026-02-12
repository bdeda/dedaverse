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
__all__ = ['check_for_updates', 'get_installed_version', 'get_latest_release_name', 'is_dev_mode']

import logging
import os
from importlib.metadata import PackageNotFoundError, version as get_package_version

import requests
from packaging.version import InvalidVersion, Version

log = logging.getLogger(__name__)

_DEFAULT_GITHUB_API = 'https://api.github.com'
_REPO_OWNER = 'bdeda'
_REPO_NAME = 'dedaverse'
_PACKAGE_NAME = 'dedaverse'


def get_installed_version() -> str | None:
    """Return the installed Dedaverse package version, or None if running in dev (not installed).

    Returns:
        Version string (e.g. '0.1.0') or None when package is not installed (dev mode).
    """
    try:
        return get_package_version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return None


def is_dev_mode() -> bool:
    """Return True if running from source / not installed (dev mode)."""
    return get_installed_version() is None


def get_latest_release_name(owner: str, repo: str) -> Version | None:
    """Fetch the latest release version from a GitHub repository.

    Uses the DEDAVERSE_GITHUB_API_ROOT_URL env var (or the misspelling
    DEDAVERSE_GITUB_API_ROOT_URL for backward compatibility) to allow mapping to an
    internal GitHub Enterprise server.

    Args:
        owner: GitHub repository owner (e.g. 'bdeda').
        repo: Repository name (e.g. 'dedaverse').

    Returns:
        Parsed Version of the latest release tag, or None on error or 404.
    """
    root = (
        os.getenv('DEDAVERSE_GITHUB_API_ROOT_URL')
        or os.getenv('DEDAVERSE_GITUB_API_ROOT_URL', _DEFAULT_GITHUB_API)
    )
    base = root.rstrip('/')
    if not base.startswith('http'):
        base = 'https://' + base.lstrip('://')
    url = f'{base}/repos/{owner}/{repo}/releases/latest'
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            log.debug('No latest release found for %s/%s', owner, repo)
            return None
        response.raise_for_status()
        data = response.json()
        log.debug(data)
        raw = data.get('tag_name') or data.get('name') or '0.0.0'
        if isinstance(raw, str) and raw.startswith('v'):
            raw = raw[1:]
        return Version(raw)
    except (requests.RequestException, InvalidVersion, KeyError) as err:
        log.debug('Failed to get latest release for %s/%s: %s', owner, repo, err)
        return None


def check_for_updates() -> tuple[bool, str | None]:
    """Check if a newer Dedaverse release is available on GitHub.

    Skips the check when running in dev mode (package not installed). Compares
    the installed version with the latest release at https://github.com/bdeda/dedaverse.

    Returns:
        (update_available, latest_version_str): True and version string if an update
        is available; False and None otherwise. When in dev mode, returns (False, None).
    """
    if is_dev_mode():
        log.debug('Skipping update check (dev mode).')
        return False, None

    current_str = get_installed_version()
    if not current_str:
        return False, None
    try:
        current = Version(current_str)
    except InvalidVersion:
        log.debug('Installed version not parseable: %s', current_str)
        return False, None

    latest = get_latest_release_name(_REPO_OWNER, _REPO_NAME)
    if latest is None:
        return False, None

    log.info('Latest release is %s; current is %s', latest, current)
    if latest > current:
        return True, str(latest)
    return False, None


if __name__ == '__main__':
    import deda.log

    deda.log.initialize(logging.DEBUG)
    available, ver = check_for_updates()
    print(f'Update available: {available}, latest: {ver}')
    