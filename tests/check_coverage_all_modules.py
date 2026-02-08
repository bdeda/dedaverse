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
"""
Check that every Python module under src/deda has test coverage > 0%.

Reads coverage.xml (Cobertura format) and warns (does not fail) if any
source file has line-rate 0 or is missing from the report.

Run after: pytest tests/ --cov=src/deda --cov-report=xml ...
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def normalize_path(p: str) -> str:
    return str(Path(p).resolve().as_posix()).lower()


def collect_source_files(source_root: Path) -> set[str]:
    """All .py files under source_root, normalized."""
    out = set()
    for path in source_root.rglob("*.py"):
        out.add(normalize_path(path))
    return out


def parse_coverage_xml(xml_path: Path, repo_root: Path) -> dict[str, float]:
    """Return mapping of normalized absolute file path -> line-rate (0.0 to 1.0)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result = {}
    for cls in root.iter("class"):
        filename = cls.get("filename")
        line_rate_str = cls.get("line-rate")
        if filename is None or line_rate_str is None:
            continue
        try:
            rate = float(line_rate_str)
        except ValueError:
            continue
        p = Path(filename)
        if not p.is_absolute():
            p = repo_root / filename
        result[normalize_path(str(p))] = rate
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "xml",
        nargs="?",
        default="coverage.xml",
        help="Path to coverage.xml (default: coverage.xml)",
    )
    parser.add_argument(
        "--source",
        default="src/deda",
        help="Source root to require coverage for (default: src/deda)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob pattern for files to exclude from the check (can repeat)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    xml_path = Path(args.xml)
    if not xml_path.is_absolute():
        xml_path = repo_root / xml_path
    source_root = repo_root / args.source

    if not xml_path.exists():
        print(f"Error: coverage XML not found: {xml_path}", file=sys.stderr)
        return 1
    if not source_root.is_dir():
        print(f"Error: source root not found: {source_root}", file=sys.stderr)
        return 1

    source_files = collect_source_files(source_root)
    # Apply exclusions (e.g. __init__2.py, deda.dcc, deda.core.ai)
    for pattern in args.exclude:
        for f in list(source_files):
            if pattern in f or Path(f).match(pattern):
                source_files.discard(f)

    rates = parse_coverage_xml(xml_path, repo_root)

    missing = []
    zero_coverage = []
    for f in sorted(source_files):
        rate = rates.get(f)
        if rate is None:
            missing.append(f)
        elif rate == 0.0:
            zero_coverage.append(f)

    if missing or zero_coverage:
        print("Warning: coverage > 0% check (some modules have no coverage):", file=sys.stderr)
        if missing:
            print("  Files missing from coverage report (0%):", file=sys.stderr)
            for m in missing:
                print(f"    {m}", file=sys.stderr)
        if zero_coverage:
            print("  Files with 0% line coverage:", file=sys.stderr)
            for z in zero_coverage:
                print(f"    {z}", file=sys.stderr)
        return 0  # Warn only; do not fail

    print("All modules have coverage > 0%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
