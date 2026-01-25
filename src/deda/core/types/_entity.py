
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

class Entity(object):
    """Base type for all types."""
    
    def __init__(self, name, parent):
        super().__init__()
        
        self._name = name
        self._parent = parent
        
        
    @classmethod
    def from_path(cls, path):
        """Get the entity of a certain type from the given path. It the path is not 
        something that represents a given type, return None.
        
        Args:
            path: (str) The file path string.
            
        Returns:
            Entity subclass instance or None.
        
        """
        raise NotImplementedError