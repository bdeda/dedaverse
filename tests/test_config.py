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

def test_config():

    from deda.core import LayeredConfig
    
    cfg1 = LayeredConfig()
    cfg2 = LayeredConfig.instance()
    assert cfg1 == cfg2
    cfg3 = LayeredConfig()
    assert cfg1 == cfg3
    
    # TODO: test editing and saving
    
