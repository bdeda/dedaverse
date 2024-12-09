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

import deda.app


@click.group()
def dedaverse():
    pass


@dedaverse.command()
def run():
    return deda.app.run()
    
    
@dedaverse.command()
def install(self):
    """Install the dedaverse startup script that will run the dedaverse app."""
    cmd_path = fr'C:\Users\{getpass.getuser()}\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\dedaverse.cmd'
    if os.path.isfile(cmd_path):
        pass
    


if __name__ == '__main__':
    sys.exit(dedaverse())
    