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
"""This is the event filter class that handles the drag and mouse move events for the DCCs that are dedaverse enabled.

The goal of this event filter is to catch when a dedaverse object is dragged and dropped into a DCC application. It will
be up to the DCC plugin to provide a handler for the drag/drop events and do any DCC sepecific logic to handle the object.

"""

__all__ = ['install_event_filter']

import logging
import json

from PySide6 import QtGui, QtCore, QtWidgets

from ._main_window import get_top_window


log = logging.getLogger('deda.eventfilter')


class EventFilter(QtCore.QObject):
    
    dragEnter = QtCore.Signal(object, object) 
    dragMove = QtCore.Signal(object, object, object)
    drop = QtCore.Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._dragged_object = None

    def handle_drag_enter(self, obj, event):
        """Handle the drag enter event. This will get the 
        dragged dedaverse object from the metadata, and 
        track the drag move event, providing a reference 
        to the tracked object to the handler via the signals.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        if self._dragged_object:
            return
        if not event.mimeData():
            return        
        text = event.mimeData().text()
        if not text:
            return
        self._dragged_object = json.loads(text)
        # TODO: handle more filtering to the specific mime data structure 
        log.debug(self._dragged_object)
        self.dragEnter.emit(obj, self._dragged_object)
        event.accept() 
        
    def handle_drag_move(self, obj, event):
        """Handle the drag move event.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        if not self._dragged_object:
            # We are not tracking a drag event, so early out.
            return        
        mouse_pos = obj.mapFromGlobal(QtGui.QCursor.pos())
        # TODO: emit signal with obj and mouse_pos
        self.dragMove.emit(obj, mouse_pos, self._dragged_object)
        
    def handle_drop(self, obj, event):
        """Handle the drop or mouseButtonRelease events.
        
        Args:
            obj: The Qt window object from the original event.
            event: The original event object.
            
        Returns:
            None 

        """
        if not self._dragged_object:
            return
        # release the mime data we were tracking.
        log.debug(f'{self._dragged_object} dropped!')
        self._dragged_object = None
        event.accept()

    def eventFilter(self, obj, event):
        """Event filter override.
        
        Args:
            obj: The QObject target for the event.
            event: The event object.
            
        Returns:
            None 
            
        """
        if event.type() in (QtCore.QEvent.Drop, QtCore.QEvent.MouseButtonRelease):
            self.handle_drop(obj, event)
        elif event.type() == QtCore.QEvent.DragEnter:
            self.handle_drag_enter(obj, event)
        elif event.type() == QtCore.QEvent.DragMove:
            self.handle_drag_move(obj, event)
        return False


def install_event_filter(handler, widget=None):
    """Install the event filter for the application. This function should be called in the startup
    processes of the GUI modes of the various applications that we support. The caller should be 
    an installed startup script for the DCC application and provide the handler that DCC plugin 
    will use to handle the dedaverse object on the DCC side via import, reference, manual construction, 
    move, augmentation, etc.
    
    Args:
        handler: (object) The object that will handle the signals emitted from the eventfilter.
        widget: The optional QObject widget that we can isolate teh event filter to. 
                Defaults to the top window of the application.
                
    Returns:
        None
        
    """
    window = widget or get_top_window()
    filter_obj = EventFilter(parent=window)
    QtWidgets.QApplication.instance().installEventFilter(filter_obj)