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
"""Locate Blender installs on Windows, macOS and Linux."""
__all__ = ['BLENDER_ENV_VAR', 'find_blender', 'iter_blender_installs']

import os
import platform
import re
import shutil
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

BLENDER_ENV_VAR = 'DEDAVERSE_BLENDER'


def find_blender(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the Blender executable to use, or None when Blender cannot be found.

    The ``DEDAVERSE_BLENDER`` environment variable wins when it names an existing file.
    Otherwise the newest install from :func:`iter_blender_installs` is used, then ``blender`` on PATH.

    Args:
        env: Environment to read (defaults to ``os.environ``).

    Returns:
        Path to the Blender executable, or None.
    """
    env = os.environ if env is None else env
    override = env.get(BLENDER_ENV_VAR, '').strip()
    if override and Path(override).is_file():
        return Path(override)
    installs = sorted(iter_blender_installs(), key=lambda item: _version_key(item[0]), reverse=True)
    if installs:
        return installs[0][1]
    on_path = shutil.which('blender')
    return Path(on_path) if on_path else None


def iter_blender_installs(system: str | None = None, roots: list[Path] | None = None
                          ) -> Iterator[tuple[str, Path]]:
    """Yield ``(version, executable)`` for each Blender found in the standard install locations.

    Args:
        system: ``platform.system()`` value to search for (defaults to the running OS).
        roots: Directories to search instead of the platform defaults (used by tests).

    Yields:
        The version label (e.g. ``'5.2'``, or ``''`` when unknown) and the executable path.
    """
    relative_exe, default_roots = _layout(system or platform.system())
    for root in default_roots() if roots is None else roots:
        for candidate in _blender_folders(root):
            exe = candidate / relative_exe
            if exe.is_file():
                yield _version_from_name(candidate.name), exe


# --- Internal -------------------------------------------------------------------------

def _blender_folders(root: Path) -> list[Path]:
    """Sub-folders of ``root`` whose name mentions Blender (install folders or app bundles)."""
    if not root.is_dir():
        return []
    return [c for c in sorted(root.iterdir()) if c.is_dir() and 'blender' in c.name.lower()]


def _layout(system: str) -> tuple[str, Callable[[], list[Path]]]:
    """Executable path inside an install folder, and a function returning the folders to search."""
    if system == 'Windows':
        return 'blender.exe', _windows_roots
    if system == 'Darwin':  # the install folder is the app bundle, e.g. Blender.app
        return 'Contents/MacOS/Blender', lambda: [Path('/Applications'), Path.home() / 'Applications']
    return 'blender', lambda: [Path('/opt'), Path('/usr/local'), Path.home() / 'blender']


def _version_from_name(name: str) -> str:
    """Pull ``major.minor`` out of a folder name such as ``Blender 5.2`` or ``blender-4.5.1-linux-x64``."""
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', name)
    return match.group(1) if match else ''


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split('.')) if version else (0,)


def _windows_roots() -> list[Path]:
    roots = []
    for var in ('ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(var)
        if base:
            roots.append(Path(base) / 'Blender Foundation')
    roots.append(Path('C:/Program Files (x86)/Steam/steamapps/common'))
    return roots
