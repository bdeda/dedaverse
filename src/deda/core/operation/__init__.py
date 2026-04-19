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
"""Operation — localhost task-loop server that drives the Copilot CLI.

The server binds to ``HOST:PORT`` and wakes every ``TICK_INTERVAL_SEC`` seconds
to: discover tasks, decide which are runnable, compose a prompt from a
template plus the task body, and invoke the ``copilot`` CLI.

Task discovery, readiness evaluation, and template storage are all
intentionally stubbed — they are placeholders that keep the loop shape
visible while the real policy gets designed.

Run as: ``py -3.13 -m deda.core.operation``
"""

from ._config import HOST, PORT, TASKS_DIR, TEMPLATES_DIR, TICK_INTERVAL_SEC
from ._prompts import compose_prompt, load_template
from ._runner import CopilotRunner, RunnerResult
from ._server import OperationServer, start_server
from ._tasks import Task, TaskStatus, discover_tasks, is_ready_to_run

__all__ = [
    'HOST',
    'PORT',
    'TASKS_DIR',
    'TEMPLATES_DIR',
    'TICK_INTERVAL_SEC',
    'CopilotRunner',
    'OperationServer',
    'RunnerResult',
    'Task',
    'TaskStatus',
    'compose_prompt',
    'discover_tasks',
    'is_ready_to_run',
    'load_template',
    'start_server',
]
