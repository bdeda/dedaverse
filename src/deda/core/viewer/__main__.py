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
"""Main entry point for the Dedaverse viewer application."""

import sys
from pathlib import Path
import logging

import click
from PySide6 import QtCore, QtGui, QtWidgets

import deda.log
from deda.app import Application
from deda.app import _main_window as _app_main_window
from deda.core.viewer import _window


log = logging.getLogger('deda.core.viewer')

# Splash size and text (temp image; replace with branded asset later)
_SPLASH_WIDTH = 420
_SPLASH_HEIGHT = 220


def _make_splash_pixmap() -> QtGui.QPixmap:
    """Build a temporary splash image so users see the app is booting."""
    pixmap = QtGui.QPixmap(_SPLASH_WIDTH, _SPLASH_HEIGHT)
    pixmap.fill(QtGui.QColor(28, 32, 38))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    # Title
    font = QtGui.QFont()
    font.setPointSize(18)
    font.setWeight(QtGui.QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(240, 242, 245))
    painter.drawText(
        pixmap.rect().adjusted(0, 50, 0, -60),
        QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.TextFlag.TextWordWrap,
        "Dedaverse Viewer",
    )
    # Loading line
    font.setPointSize(11)
    font.setWeight(QtGui.QFont.Weight.Normal)
    painter.setFont(font)
    painter.setPen(QtGui.QColor(160, 165, 175))
    painter.drawText(
        pixmap.rect().adjusted(0, 110, 0, -70),
        QtCore.Qt.AlignmentFlag.AlignCenter,
        "Loading…",
    )
    painter.end()
    return pixmap


@click.command()
@click.argument('usd_path', required=False, type=click.Path(exists=False))
def viewer(usd_path):
    """Run the Dedaverse viewer, optionally opening a USD file.

    USD_PATH is an optional path to a USD file (.usd, .usda, .usdc, .usdz)
    to open when the viewer starts.
    """
    deda.log.initialize(loglevel=logging.INFO)
    app = Application()
    icon_path = Path(_app_main_window.__file__).parent / 'icons' / 'star_icon.png'
    if icon_path.is_file():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    # Show splash so users know the viewer is booting
    splash_pix = _make_splash_pixmap()
    splash = QtWidgets.QSplashScreen(splash_pix, QtCore.Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    QtWidgets.QApplication.processEvents()
    w = _window.MainWindow()
    w.show()
    splash.finish(w)
    if usd_path:
        path_str = str(Path(usd_path).resolve())
        QtCore.QTimer.singleShot(0, lambda: w._open_stage_file(path_str))
    return app.exec()


if __name__ == '__main__':
    sys.exit(viewer())