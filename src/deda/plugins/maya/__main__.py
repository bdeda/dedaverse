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
"""Launch Maya 2027 with the dedaverse environment: ``python -m deda.plugins.maya [args]``."""
import sys


def main(argv=None):
    from . import MAYA_VERSION
    import deda.core
    plugin = deda.core.PluginRegistry().get(f'Maya {MAYA_VERSION}')
    try:
        plugin.launch(*(sys.argv[1:] if argv is None else argv))
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
