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
import sys
import os
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
    """Install the dedaverse startup script."""
    
    # TODO: This should create a venv if one does not already exist for the current dedaverse git clone.
    
    cmd_path = fr'C:\Users\{getpass.getuser()}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\dedaverse.cmd'
    bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'bin', 'dedaverse.bat'))
    if os.path.isfile(bat_path):
        with open(cmd_path, 'w') as f:
            f.write(f'@echo off\nstart {bat_path}\n')
        print(f'Startup script installed to {cmd_path}')
        return 0
    print('Install errors!')
    return 1
    

if __name__ == '__main__':
    sys.exit(dedaverse())
    