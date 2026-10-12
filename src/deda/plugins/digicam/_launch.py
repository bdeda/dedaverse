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
"""Discover and launch Photoshop / Lightroom Classic / Lightroom with an image file.

Lightroom Classic and Lightroom (cloud) are catalog-based and do not reliably support
opening an arbitrary file via a command-line path the way Photoshop does. This module
still passes the path through for all three (best effort); Lightroom variants may just
launch without loading the image if they ignore the argument.
"""
__all__ = ['APP_LABELS', 'find_app', 'open_in_app']

import glob
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

APP_LABELS = {
    'photoshop': 'Photoshop',
    'lightroom_classic': 'Lightroom Classic',
    'lightroom': 'Lightroom',
}

_ENV_VARS = {
    'photoshop': 'DIGICAM_PHOTOSHOP_EXE',
    'lightroom_classic': 'DIGICAM_LIGHTROOM_CLASSIC_EXE',
    'lightroom': 'DIGICAM_LIGHTROOM_EXE',
}

# Relative to a Program Files directory.
_GLOB_PATTERNS = {
    'photoshop': ['Adobe/Adobe Photoshop*/Photoshop.exe'],
    'lightroom_classic': ['Adobe/Adobe Lightroom Classic/Lightroom.exe'],
    'lightroom': ['Adobe/Adobe Lightroom/Lightroom.exe'],
}


def _program_files_dirs() -> list[str]:
    dirs = []
    for var in ('PROGRAMFILES', 'PROGRAMFILES(X86)'):
        value = os.environ.get(var)
        if value:
            dirs.append(value)
    return dirs or [r'C:\Program Files', r'C:\Program Files (x86)']


def find_app(app_key: str) -> str | None:
    """Find the executable for app_key, checking its env var override then default install paths.

    Args:
        app_key: One of 'photoshop', 'lightroom_classic', 'lightroom'.

    Returns:
        str: Full path to the executable, or None if not found.

    """
    override = os.environ.get(_ENV_VARS[app_key])
    if override and Path(override).is_file():
        return override
    for base in _program_files_dirs():
        for pattern in _GLOB_PATTERNS[app_key]:
            for match in glob.glob(str(Path(base) / pattern)):
                if Path(match).is_file():
                    return match
    return None


def open_in_app(app_key: str, image_path: Path) -> None:
    """Launch the given app with image_path. Raises FileNotFoundError if the app can't be found."""
    label = APP_LABELS[app_key]
    exe = find_app(app_key)
    if not exe:
        raise FileNotFoundError(
            f'Could not find {label}. Set the {_ENV_VARS[app_key]} environment variable to its '
            f'executable path, or install it in the default location.'
        )
    subprocess.Popen([exe, str(image_path)])
    log.info(f'Launched {label} with {image_path}')
