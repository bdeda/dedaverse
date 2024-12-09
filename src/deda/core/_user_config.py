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
__all__ = ['UserConfig']

import os
import json

class UserConfig:
    
    def __init__(self):        
        self._path = os.path.expanduser('~/dedaverse/user.cfg')
        self._data = dict()
        if not os.path.isfile(self._path):
            return
        with open(self._path, 'r') as f:
            self._data = json.load(f)
            
    @property
    def p4_host(self):
        return self._data.get('p4_host')
    
    @p4_host.setter
    def p4_host(self, value):
        self._data['p4_host'] = value
    
    @property
    def p4_client(self):
        return self._data.get('p4_client')
    
    @p4_client.setter
    def p4_client(self, value):
        self._data['p4_host'] = value    
    
    @property
    def p4_user(self):
        return self._data.get('p4_user')
    
    @p4_user.setter
    def p4_user(self, value):
        self._data['p4_user'] = value    
        
    @property
    def projects(self):
        return self._data.get('projects', list())
    
    def add_project(self, project):
        if 'projects' not in self._data:
            self._data['projects'] = list()
        if project in self._data['projects']:
            return 
        self._data['projects'].append(project)
        
    def remove_project(self, project):
        for my_project in self.projects:
            if project == my_project:
                self._data['projects'].remove(project)
                return            
            
    def save(self):
        """Save the user settings"""
        dirname = os.path.dirname(self._path)
        try:
            os.makedirs(dirname)
        except OSError:
            pass
        with open(self._path, 'w') as f:
            json.dump(self._data, f, indent=4, sort_keys=True)