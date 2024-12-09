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
__all__ = ['Project']


class Project:
    
    def __init__(self, name, **kwargs):
        self._name = name
        self._data = kwargs
        
    @property
    def name(self):
        return self._name
        
    def __eq__(self, other):
        if isinstance(other, Project) and self.name == other.name:
            return True
        try:
            return self.name == other['name']
        except KeyError:
            pass
        return False
        
    def as_dict(self):
        data = copy.deepcopy(self._data)
        data['name'] = self._name
        