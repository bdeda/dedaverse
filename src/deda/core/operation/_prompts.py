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
"""Prompt template loader and composer.

Templates live under :data:`deda.core.operation.TEMPLATES_DIR`
(``src/deda/core/operation/templates/``). Each template is a Markdown file
that may reference ``{task_title}`` and ``{task_body}`` placeholders via
``str.format_map`` — unknown placeholders are left untouched so templates
fail safe when the task schema grows.

TODO: Final storage location is still TBD — we may move templates into a
user-editable path (``~/.dedaverse/operation/templates/``) once the shape
of a template is stable.
"""

from pathlib import Path

from ._config import TEMPLATES_DIR
from ._tasks import Task

__all__ = ['compose_prompt', 'load_template']


class _SafeFormatDict(dict[str, object]):
    """``str.format_map`` helper that leaves unknown keys as ``{key}``."""

    def __missing__(self, key: str) -> str:
        return '{' + key + '}'


def load_template(name: str | None = None, templates_dir: Path | None = None) -> str:
    """Load a template by name (no extension). Falls back to ``default``.

    Args:
        name: Template name without ``.md``. ``None`` → ``default``.
        templates_dir: Override the lookup directory (tests).

    Raises:
        FileNotFoundError: If neither the requested template nor ``default.md``
            exist under ``templates_dir``.
    """
    directory = templates_dir if templates_dir is not None else TEMPLATES_DIR
    requested = directory / f'{name or "default"}.md'
    if requested.is_file():
        return requested.read_text(encoding='utf-8')
    fallback = directory / 'default.md'
    if fallback.is_file():
        return fallback.read_text(encoding='utf-8')
    raise FileNotFoundError(f'No template found at {requested} (and no default.md in {directory})')


def compose_prompt(task: Task, templates_dir: Path | None = None) -> str:
    """Render the final prompt string passed to the Copilot CLI."""
    template = load_template(task.template, templates_dir=templates_dir)
    return template.format_map(_SafeFormatDict(task_title=task.title, task_body=task.body))
