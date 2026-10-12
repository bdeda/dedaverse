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
"""Use the viewer's saved notes as art direction.

The viewer's *Save Notes* writes ``annotations_<time>.json`` (the note text, the free-text annotations and
the strokes) and ``snapshot_<time>.png`` (the viewport with the annotations drawn on it) side by side. The
text becomes written art direction for the prompt and the snapshot becomes the reference image.
"""
import json
from pathlib import Path


def notes_to_direction(payload: dict) -> str:
    """The written art direction in a notes payload: the note's description, then each text annotation.

    Args:
        payload: The parsed notes JSON.

    Returns:
        The lines joined with newlines; empty if the notes hold no text.
    """
    lines = []
    description = str(payload.get('description') or '').strip()
    if description:
        lines.append(description)
    for text in payload.get('texts') or []:
        content = str((text or {}).get('text') or '').strip()
        if content:
            lines.append(content)
    return '\n'.join(lines)


def load_notes(json_path: str | Path) -> tuple[str, Path | None]:
    """Read saved notes.

    Args:
        json_path: An ``annotations_*.json`` file written by the viewer.

    Returns:
        ``(direction, snapshot)``: the written art direction and the matching ``snapshot_*.png`` if it exists.

    Raises:
        FileNotFoundError: If ``json_path`` does not exist.
        ValueError: If the file is not valid notes JSON.
    """
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f'Notes not found: {path}')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except ValueError as err:
        raise ValueError(f'{path.name} is not valid notes JSON: {err}') from err
    if not isinstance(payload, dict):
        raise ValueError(f'{path.name} is not valid notes JSON: expected an object')
    snapshot = path.with_name(path.name.replace('annotations_', 'snapshot_', 1)).with_suffix('.png')
    return notes_to_direction(payload), snapshot if snapshot.is_file() else None
