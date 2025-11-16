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
__all__ = ['initialize']


import logging
import coloredlogs


def initialize(loglevel=logging.DEBUG):
    """Initialize the logger for the given log level.
    
    Args:
        loglevel: (str) The loglevel string.
        
    """
    logger = logging.getLogger('')
    coloredlogs.install(level=loglevel, logger=logger)