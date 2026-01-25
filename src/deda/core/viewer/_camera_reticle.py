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
"""USDView plugin for displaying a camera reticle overlay in the 3D viewport.

This plugin adds a camera reticle (crosshair) overlay to the USDView viewport,
which helps with camera framing and composition when working with USD scenes.
"""

__all__ = ['CameraReticlePlugin']

import logging
from typing import Optional

try:
    from pxr import Usd, Gf
    from pxr.Usdviewq.plugin import PluginContainer
    from pxr.Usdviewq.stageView import StageView
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    PluginContainer = object
    StageView = object

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QtWidgets = None
    QtCore = None
    QtGui = None


log = logging.getLogger(__name__)


class CameraReticleOverlay:
    """Overlay widget that draws a camera reticle on top of the viewport."""
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize the reticle overlay.
        
        Args:
            parent: Parent widget (typically the StageView).
        """
        self._parent = parent
        self._enabled = True
        self._color = QtGui.QColor(255, 255, 255, 180)  # White with transparency
        self._line_width = 1
        self._size = 20  # Size of the reticle in pixels
        self._style = 'crosshair'  # 'crosshair', 'frame', or 'grid'
        
    @property
    def enabled(self) -> bool:
        """Whether the reticle is enabled."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        """Enable or disable the reticle."""
        self._enabled = value
        if self._parent:
            self._parent.update()
    
    @property
    def color(self) -> QtGui.QColor:
        """Reticle color."""
        return self._color
    
    @color.setter
    def color(self, value: QtGui.QColor):
        """Set reticle color."""
        self._color = value
        if self._parent:
            self._parent.update()
    
    @property
    def size(self) -> int:
        """Reticle size in pixels."""
        return self._size
    
    @size.setter
    def size(self, value: int):
        """Set reticle size."""
        self._size = max(5, min(100, value))  # Clamp between 5 and 100
        if self._parent:
            self._parent.update()
    
    @property
    def style(self) -> str:
        """Reticle style: 'crosshair', 'frame', or 'grid'."""
        return self._style
    
    @style.setter
    def style(self, value: str):
        """Set reticle style."""
        if value in ('crosshair', 'frame', 'grid'):
            self._style = value
            if self._parent:
                self._parent.update()
    
    def draw(self, painter: QtGui.QPainter, rect: QtCore.QRect):
        """Draw the reticle overlay.
        
        Args:
            painter: QPainter instance for drawing.
            rect: Viewport rectangle.
        """
        if not self._enabled:
            return
        
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(self._color, self._line_width))
        
        center_x = rect.width() / 2
        center_y = rect.height() / 2
        half_size = self._size / 2
        
        if self._style == 'crosshair':
            # Draw crosshair (simple cross)
            painter.drawLine(
                center_x - half_size, center_y,
                center_x + half_size, center_y
            )
            painter.drawLine(
                center_x, center_y - half_size,
                center_x, center_y + half_size
            )
            
        elif self._style == 'frame':
            # Draw frame (rule of thirds grid)
            third_w = rect.width() / 3
            third_h = rect.height() / 3
            
            # Vertical lines
            painter.drawLine(third_w, 0, third_w, rect.height())
            painter.drawLine(third_w * 2, 0, third_w * 2, rect.height())
            
            # Horizontal lines
            painter.drawLine(0, third_h, rect.width(), third_h)
            painter.drawLine(0, third_h * 2, rect.width(), third_h * 2)
            
            # Center crosshair
            painter.drawLine(
                center_x - half_size, center_y,
                center_x + half_size, center_y
            )
            painter.drawLine(
                center_x, center_y - half_size,
                center_x, center_y + half_size
            )
            
        elif self._style == 'grid':
            # Draw grid pattern
            spacing = 20
            # Vertical lines
            x = spacing
            while x < rect.width():
                painter.drawLine(x, 0, x, rect.height())
                x += spacing
            
            # Horizontal lines
            y = spacing
            while y < rect.height():
                painter.drawLine(0, y, rect.width(), y)
                y += spacing
            
            # Center crosshair
            painter.drawLine(
                center_x - half_size, center_y,
                center_x + half_size, center_y
            )
            painter.drawLine(
                center_x, center_y - half_size,
                center_x, center_y + half_size
            )
        
        painter.restore()


class CameraReticlePlugin(PluginContainer):
    """USDView plugin that adds a camera reticle overlay to the viewport."""
    
    def registerPlugins(self, plugRegistry, plugCtx, plugPrefs):
        """Register the plugin with USDView.
        
        This method is called by USDView to register the plugin.
        
        Args:
            plugRegistry: Plugin registry from USDView.
            plugCtx: Plugin context.
            plugPrefs: Plugin preferences.
        """
        if not USD_AVAILABLE:
            log.warning('USD libraries not available. CameraReticlePlugin will not be registered.')
            return
        
        # Register the plugin
        plugRegistry.registerCommandPlugin(
            "CameraReticlePlugin.toggle",
            "Toggle Camera Reticle",
            lambda: self._toggle_reticle(plugCtx)
        )
        
        # Initialize the overlay
        self._overlay = CameraReticleOverlay()
        self._stage_view: Optional[StageView] = None
        self._original_paint_event = None
        
    def configureView(self, stageView: StageView):
        """Configure the view when it's created.
        
        Args:
            stageView: The StageView instance to configure.
        """
        if not USD_AVAILABLE or not PYSIDE6_AVAILABLE:
            return
        
        self._stage_view = stageView
        self._overlay._parent = stageView
        
        # Override the paintEvent to draw the reticle
        if hasattr(stageView, 'paintEvent'):
            self._original_paint_event = stageView.paintEvent
            stageView.paintEvent = self._paint_event_with_reticle
        
        log.debug('Camera reticle plugin configured for viewport')
    
    def _paint_event_with_reticle(self, event):
        """Custom paint event that draws the reticle overlay.
        
        Args:
            event: QPaintEvent from Qt.
        """
        # Call the original paint event first
        if self._original_paint_event:
            self._original_paint_event(event)
        
        # Draw the reticle overlay
        if self._overlay.enabled and self._stage_view:
            painter = QtGui.QPainter(self._stage_view)
            rect = self._stage_view.rect()
            self._overlay.draw(painter, rect)
            painter.end()
    
    def _toggle_reticle(self, plugCtx):
        """Toggle the reticle on/off.
        
        Args:
            plugCtx: Plugin context from USDView.
        """
        if self._overlay:
            self._overlay.enabled = not self._overlay.enabled
            if self._stage_view:
                self._stage_view.update()
            log.info(f'Camera reticle {"enabled" if self._overlay.enabled else "disabled"}')
    
    @property
    def overlay(self) -> Optional[CameraReticleOverlay]:
        """Get the reticle overlay instance."""
        return self._overlay


# USDView plugin registration
# USDView will automatically discover and load this plugin if it's in the plugin path
def registerPlugins(plugRegistry, plugCtx, plugPrefs):
    """Entry point for USDView plugin registration.
    
    This function is called by USDView when loading plugins.
    
    Args:
        plugRegistry: Plugin registry from USDView.
        plugCtx: Plugin context.
        plugPrefs: Plugin preferences.
    """
    if not USD_AVAILABLE:
        log.warning('USD libraries not available. CameraReticlePlugin cannot be registered.')
        return
    
    plugin = CameraReticlePlugin()
    plugin.registerPlugins(plugRegistry, plugCtx, plugPrefs)
    return plugin
