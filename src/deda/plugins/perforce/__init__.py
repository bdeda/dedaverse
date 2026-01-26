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
"""
The builtin Asset Manager plugin connects to perforce and uses p4python to handle file operations. 

"""
import os
import logging
from contextlib import contextmanager
from pathlib import Path
import P4

import deda.core


__version__ = '0.1.0'
__vendor__ = 'Deda'

log = logging.getLogger('deda.plugins.PerforceFileManager')


@contextmanager
def P4Connection():
    """The p4 plugin uses env variables to connect to Perforce. 

    """
    p4c = P4.P4()
    try:
        p4c.connect()
        yield p4c
    finally:
        p4c.disconnect()
        

class PerforceFileManager(deda.core.FileManager):
    """Uses perforce to do file operations. 
    
    """
    
    icon_path = str(Path(__file__).parent / 'p4_icon_128.png')
    
    def load(self):
        """Load the plugin."""        
        log.info('Perforce plugin loading...')
        # Should we do anything here?
        log.info('Perforce loaded successfully.')
                
    def can_handle(self, files):
        """Check to see if the given files are the types of files this plugin can handle. 
        
        Args:
            files: (list(str)) The fiel or files to check.
            
        Returns:
            list: The list of bools on if the file can be handled by this plugin.
            
        """
        raise NotImplementedError    
    
    def add(self, files):
        """Add files to the file management system.
        
        Args: 
            files: (list(str)) Add a file to the file management system.
            
        """
        raise NotImplementedError
    
    def rename(self, file, new_name):
        """Rename a file in the file management system.
        
        Args: 
            file: (str) The source file to rename.
            new_name: (str) The new name for the file.
            
        """
        raise NotImplementedError
    
    def delete(self, files):
        """Delete files from the file management system.
        
        Args: 
            files: (list(str)) Delete a file from the file management system.
            
        """
        raise NotImplementedError
    
    def get_latest(self, files):
        """Get the latest version of files from the file management system.
        
        Args: 
            files: (list(str)) Get latest versions of the files from the file management system.
            
        """
        raise NotImplementedError 
    
    def get_version(self, file, version):
        """Get the given version of an asset from the asset system.
        
        Args: 
            file: (str) Get the specific version of the file from the file management system.
            version: (int) The version number.
            
        """
        raise NotImplementedError    
    
    def checkout(self, files):
        """Checkout the files from the file management system. This is an exclusive checkout.
        
        Args: 
            files: (list(str)) Check out the file from the file management system.
            
        """
        raise NotImplementedError
    
    def commit(self, files, message):
        """Commit the files to the file management system. 
        
        Args: 
            files: (list(str)) Files to commit.
            message: (str) The commit message.
            
        """
        raise NotImplementedError     
        
        
deda.core.PluginRegistry().register(PerforceFileManager('PerforceFileManager', __version__, __vendor__, 
                                                        image=PerforceFileManager.icon_path, 
                                                        description=PerforceFileManager.__doc__))