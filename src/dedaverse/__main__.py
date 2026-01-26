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
import sys
import os
import platform
from pathlib import Path
import click
import getpass

# Conditional debugger import (only on Windows and when WING_DEBUG env var is set)
if platform.system() == 'Windows' and os.getenv('WING_DEBUG'):
    try:
        wing_path = Path(r'C:\Program Files\Wing Pro 10')
        if wing_path.exists():
            sys.path.insert(0, str(wing_path))
            import wingdbstub
    except ImportError:
        pass
    finally:
        if sys.path and sys.path[0] == str(wing_path):
            sys.path = sys.path[1:]

import deda.app


@click.group()
def dedaverse():
    pass


@dedaverse.command()
def run():
    """Run the app in the system tray."""
    return deda.app.run()
    
    
@dedaverse.command()
def install():
    """Install the dedaverse startup script.
    
    On Windows: Creates a startup script in the user's Startup folder.
    On Linux/macOS: Creates a systemd user service or launchd agent (not yet implemented).
    """
    
    # TODO: This should create a venv if one does not already exist for the current dedaverse git clone.
    
    if platform.system() == 'Windows':
        # Windows: Install to Startup folder
        startup_dir = Path.home() / 'AppData' / 'Roaming' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
        startup_dir.mkdir(parents=True, exist_ok=True)
        cmd_path = startup_dir / 'dedaverse.cmd'
        
        # Get bat_path relative to this file
        bat_path = Path(__file__).parent.parent.parent / 'bin' / 'dedaverse.bat'
        bat_path = bat_path.resolve()
        
        if bat_path.is_file():
            with open(cmd_path, 'w') as f:
                f.write(f'@echo off\nstart "{bat_path}"\n')
            print(f'Startup script installed to {cmd_path}')
            return 0
        else:
            print(f'Error: Could not find dedaverse.bat at {bat_path}')
            return 1
    else:
        # Linux/macOS: Not yet implemented
        print(f'Autostart installation is not yet implemented for {platform.system()}.')
        print('You can manually add dedaverse to your system startup.')
        raise click.ClickException('Autostart installation is not yet implemented for this platform.')
    

if __name__ == '__main__':
    sys.exit(dedaverse())
    