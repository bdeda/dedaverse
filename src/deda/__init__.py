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

from . import core
#try:
    #from . import app
#except ImportError as err:
    ## I am getting this import error on ubuntu when running github actions.
    ## ImportError: libEGL.so.1: cannot open shared object file: No such file or directory
    #print(err) 
    #if 'libEGL.so' not in str(err):
        #raise
