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

__all__ = ['iter_photoshop_installs']

import os
import platform


def iter_photoshop_installs():
    """Find a locally installed version of Photoshop."""
    if platform.system() != 'Windows':
        return
    # look in the normal install location
    rootdir = r'C:\Program Files\Adobe'
    for item in os.listdir(rootdir):
        if 'Photoshop' not in item:
            continue
        d = os.path.join(rootdir, item)
        if not os.path.isdir(d):
            continue
        expected = os.path.join(d, 'Photoshop.exe')
        if os.path.isfile(expected):
            yield item, expected
            
        