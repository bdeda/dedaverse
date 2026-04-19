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
"""Task discovery and readiness checks.

TODO: Both :func:`discover_tasks` and :func:`is_ready_to_run` are stubs.
The real discovery source (Jira, filesystem drop-box, REST, etc.) and the
readiness policy (schedule, dependencies, quiet hours, budget) still need
to be decided. Keep the signatures stable — the loop in
:mod:`deda.core.operation._server` is written against them.
"""

from dataclasses import dataclass, field
from datetime import datetime

__all__ = ['Task', 'discover_tasks', 'is_ready_to_run']


@dataclass
class Task:
    """A unit of work the operation loop may dispatch to Copilot.

    Attributes:
        id: Stable identifier — used for logs and de-duplication.
        title: Human-readable label.
        body: Task-specific prompt text appended to the template boilerplate.
        template: Template name (see :mod:`_prompts`). ``None`` means default.
        metadata: Free-form fields used by readiness checks (due date,
            dependencies, priority, etc.) — schema TBD.
    """

    id: str
    title: str
    body: str
    template: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


def discover_tasks() -> list[Task]:
    """Return the list of known tasks.

    TODO: Replace stub with real discovery — likely reads from a directory of
    task files, a Jira JQL query, or the Operation web service once that is
    wired up.
    """
    return []


def is_ready_to_run(task: Task, now: datetime | None = None) -> bool:
    """Return True when ``task`` should be dispatched on this tick.

    TODO: Real policy (schedule / deps / budget / quiet hours). The default
    implementation simply accepts every discovered task so the loop shape
    can be tested end-to-end.
    """
    del now  # reserved for the real scheduling policy
    return True
