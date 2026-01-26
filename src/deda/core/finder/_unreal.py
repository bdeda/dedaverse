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
__all__ = []

import platform
from pathlib import Path
import glob


def iter_unreal_installs():
    """Find all installs of Unreal Engine on the system."""
    if platform.system() != 'Windows':
        return
    # Look in the normal install location
    epic_games_dir = Path('C:/Program Files/Epic Games')
    if not epic_games_dir.exists():
        return
    # Search for UnrealEditor.exe in Engine/Binaries/Win64 subdirectories
    for engine_dir in epic_games_dir.iterdir():
        if not engine_dir.is_dir():
            continue
        editor_exe = engine_dir / 'Engine' / 'Binaries' / 'Win64' / 'UnrealEditor.exe'
        if editor_exe.is_file():
            yield engine_dir.name, str(editor_exe)