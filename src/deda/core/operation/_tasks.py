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
"""Task discovery, status, and readiness checks.

Tasks live under :data:`deda.core.operation.TASKS_DIR` — one subdirectory
per task, named ``task<N>`` (e.g. ``task1``, ``task2``). Each directory
contains a ``task.md`` with optional skill.md-style YAML front-matter
followed by the task body in Markdown. Any sibling files (supporting
docs, reference images) are exposed via ``Task.metadata['attachments']``
as absolute path strings.

Status lifecycle
----------------
Every task has a :class:`TaskStatus`. Only ``Open`` tasks are dispatched;
everything else is skipped by :func:`is_ready_to_run`:

- ``Open`` — new, runnable.
- ``In-Progress`` — currently being worked on; runner should not redispatch.
- ``Blocked`` — waiting on a human or on another task to finish.
- ``Ready-for-Review`` — work is done; a human must verify before continuing.
- ``Closed`` / ``Resolved`` — terminal; no further action.

Status mutation is currently human-managed — edit ``status:`` in the
front-matter. Auto-writeback from the runner (``Open`` → ``In-Progress``
on dispatch, etc.) is a follow-up.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from . import _config

__all__ = ['Task', 'TaskStatus', 'discover_tasks', 'is_ready_to_run']


log = logging.getLogger(__name__)

_TASK_DIR_RE = re.compile(r'^task(\d+)$')


class TaskStatus(str, Enum):
    """Lifecycle state of a task. String values are the canonical form
    written to ``task.md`` front-matter."""

    OPEN = 'Open'
    IN_PROGRESS = 'In-Progress'
    BLOCKED = 'Blocked'
    READY_FOR_REVIEW = 'Ready-for-Review'
    CLOSED = 'Closed'
    RESOLVED = 'Resolved'

    @classmethod
    def parse(cls, raw: str | None) -> 'TaskStatus':
        """Parse a string from front-matter into a status.

        Case- and separator-insensitive — ``open``, ``In Progress``,
        ``ready_for_review`` all resolve. Unknown values log a warning
        and fall back to :attr:`OPEN` so a malformed task is still
        visible (as runnable) rather than silently ignored.
        """
        if raw is None or not raw.strip():
            return cls.OPEN
        normalized = re.sub(r'[\s_-]+', '', raw.strip()).lower()
        for member in cls:
            if re.sub(r'[\s_-]+', '', member.value).lower() == normalized:
                return member
        log.warning('operation: unknown task status %r — defaulting to Open', raw)
        return cls.OPEN


@dataclass
class Task:
    """A unit of work the operation loop may dispatch to Copilot.

    Attributes:
        id: Stable identifier — the task directory name (``task<N>``).
        title: Human-readable label (front-matter ``title``, falling back
            to the first ``# H1`` in the body, else the directory name).
        body: Markdown body that follows the front-matter; appended to the
            prompt template.
        template: Template name (see :mod:`_prompts`). ``None`` → default.
        status: Lifecycle state. Defaults to :attr:`TaskStatus.OPEN`.
        metadata: Remaining front-matter keys plus ``attachments`` — a
            list of absolute path strings for non-``task.md`` sibling files.
    """

    id: str
    title: str
    body: str
    template: str | None = None
    status: TaskStatus = TaskStatus.OPEN
    metadata: dict[str, object] = field(default_factory=dict)


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split ``text`` into ``(front_matter, body)``.

    Front-matter is an optional ``---`` fenced block of flat ``key: value``
    lines at the top of the file. Lines without ``:`` and blank/comment
    lines inside the block are ignored. If no fence is present, returns
    ``({}, text)`` unchanged.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip('\r\n') != '---':
        return {}, text
    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].rstrip('\r\n') == '---':
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    meta: dict[str, str] = {}
    for raw in lines[1:end_idx]:
        line = raw.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, _, value = line.partition(':')
        meta[key.strip()] = value.strip()
    body = ''.join(lines[end_idx + 1:]).lstrip('\n')
    return meta, body


def _first_h1(body: str) -> str | None:
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith('# '):
            return line[2:].strip() or None
    return None


def _load_task(task_dir: Path) -> Task | None:
    task_md = task_dir / 'task.md'
    if not task_md.is_file():
        log.warning('operation: skipping %s — no task.md', task_dir)
        return None
    try:
        text = task_md.read_text(encoding='utf-8')
    except OSError as err:
        log.warning('operation: could not read %s: %s', task_md, err)
        return None

    meta, body = _parse_front_matter(text)
    title = meta.pop('title', None) or _first_h1(body) or task_dir.name
    template = meta.pop('template', None) or None
    status = TaskStatus.parse(meta.pop('status', None))

    attachments = sorted(
        str(p) for p in task_dir.iterdir() if p.is_file() and p.name != 'task.md'
    )
    metadata: dict[str, object] = dict(meta)
    metadata['attachments'] = attachments

    return Task(
        id=task_dir.name,
        title=title,
        body=body,
        template=template,
        status=status,
        metadata=metadata,
    )


def discover_tasks(tasks_dir: Path | None = None) -> list[Task]:
    """Scan ``tasks_dir`` for ``task<N>/task.md`` entries, sorted by ``N``.

    Directories that don't match ``task<N>`` or lack a ``task.md`` are
    skipped. A missing ``tasks_dir`` returns an empty list — the loop
    treats "no tasks" as a normal state, not an error.
    """
    directory = tasks_dir if tasks_dir is not None else _config.TASKS_DIR
    if not directory.is_dir():
        return []

    indexed: list[tuple[int, Path]] = []
    for child in directory.iterdir():
        if not child.is_dir():
            continue
        match = _TASK_DIR_RE.match(child.name)
        if not match:
            continue
        indexed.append((int(match.group(1)), child))
    indexed.sort(key=lambda pair: pair[0])

    tasks: list[Task] = []
    for _, task_dir in indexed:
        task = _load_task(task_dir)
        if task is not None:
            tasks.append(task)
    return tasks


def is_ready_to_run(task: Task, now: datetime | None = None) -> bool:
    """Return True when ``task`` should be dispatched on this tick.

    Gate: only :attr:`TaskStatus.OPEN` tasks are runnable. All other
    states (``In-Progress``, ``Blocked``, ``Ready-for-Review``,
    ``Closed``, ``Resolved``) are skipped and left for humans or a later
    policy layer to advance.

    TODO: Extend with schedule / dependency / budget / quiet-hours checks.
    """
    del now  # reserved for the real scheduling policy
    return task.status is TaskStatus.OPEN
