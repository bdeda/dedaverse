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
"""Standalone launcher for the Compare tool window.

Run with: python -m deda.plugins.compare

This lets Compare be added as a project "App" tile (Type: Python, Command:
"python -m deda.plugins.compare") in addition to its Dedaverse main-menu entry.
"""
import sys

from PySide6 import QtWidgets


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    from ._window import CompareWindow
    window = CompareWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
