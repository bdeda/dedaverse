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
import click
import getpass

try:
    sys.path.insert(0, r'C:\Program Files\Wing Pro 10')
    import wingdbstub
except ImportError:
    pass
finally:
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
        startup_dir = os.path.join(
            os.path.expanduser('~'),
            'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        os.makedirs(startup_dir, exist_ok=True)
        cmd_path = os.path.join(startup_dir, 'dedaverse.cmd')
        bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'bin', 'dedaverse.bat'))
        
        if os.path.isfile(bat_path):
            with open(cmd_path, 'w') as f:
                f.write(f'@echo off\nstart {bat_path}\n')
            print(f'Startup script installed to {cmd_path}')
            return 0
        else:
            print(f'Error: Could not find dedaverse.bat at {bat_path}')
            return 1
    else:
        # Linux/macOS: Not yet implemented
        print(f'Autostart installation is not yet implemented for {platform.system()}.')
        print('You can manually add dedaverse to your system startup.')
        return 1
    

if __name__ == '__main__':
    sys.exit(dedaverse())
    