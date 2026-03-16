# AGENTS.md

This file provides guidance for AI agents when generating, modifying, or reviewing code in the Dedaverse repository.

## 🎯 Project Overview

Dedaverse is a Python-based asset management system for visual media projects (films, games, etc.). It provides:
- Asset versioning and tracking
- Plugin-based extensibility
- Integration with DCC applications (Maya, Houdini, Photoshop, etc.)
- Task management integration (Jira)
- File management systems (Perforce, local filesystem)
- Qt-based UI (PySide6)

**Key Technologies:**
- Python 3.12+
- PySide6 (Qt for Python)
- dataclasses_json for configuration
- Click for CLI
- USD Core for 3D asset handling
- p4python for Perforce integration

## 📋 Core Principles

**Defined strategies for agents:** (1) **Code integrity** — preserve existing behavior; never relax or remove tests to make a change pass; fix implementation to satisfy tests. (2) **Test patterns** — use the project’s test layout, naming, fixtures, and mocks (see [Testing](#10-testing)). (3) **Testability** — write testable code and add tests for new or touched code; run the test suite after changes.

### 1. Follow Existing Patterns
- **Study the codebase first** - Understand existing patterns before making changes
- **Match the style** - Follow existing naming conventions, file structure, and code organization
- **Respect the architecture** - Don't break the plugin system, configuration layers, or UI patterns

### 2. Code Quality Standards

#### Type Hints
- **Always add type hints** to new functions and methods
- Use Python 3.12+ syntax: `str | None` instead of `Optional[str]`
- Use `from typing import` for complex types (Dict, List, Tuple, etc.)
- Example:
```python
def get_project(self, name: str) -> ProjectConfig | None:
    """Get project by name."""
    ...
```

#### Error Handling
- **Never use bare `except:`** - Always catch specific exceptions
- **Log errors with context** - Include relevant information in error messages
- **Use appropriate log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Example:
```python
try:
    plugin.load()
except (ImportError, AttributeError, ModuleNotFoundError) as err:
    log.error(f'Failed to load plugin {plugin.name}: {err}')
    log.exception(err)
except Exception as err:
    log.error(f'Unexpected error loading plugin {plugin.name}: {err}')
    log.exception(err)
```

#### Path Handling
- **Use `pathlib.Path`** instead of `os.path` for new code
- **Make paths cross-platform** - Don't hardcode Windows paths
- Example:
```python
from pathlib import Path

icon_path = Path(__file__).parent / 'icons' / 'gear_icon.png'
```

#### Resource Management
- **Use context managers** for file operations
- **Close resources properly** - Ensure files, connections, etc. are closed
- Example:
```python
with open(config_path, 'w') as f:
    json.dump(data, f, indent=4)
```

#### Module Layout
- **Public API at the top** - Put public classes and functions at the top of the module.
- **Internal/private at the bottom** - Put internal helpers and private functions (e.g. names starting with `_`) at the bottom of the module.
- **Sort alphabetically** - Within each area (top and bottom), keep symbols sorted alphabetically.
- **Classes before functions** - In the public (top) section, list classes first (alphabetically), then functions (alphabetically).
- **Within a class** - Sort method and property definitions alphabetically by name (e.g. `layer`, `metadata_dir`, `metadata_path`, `rootdir`, `stage`). Place `__init__` first, then other methods and properties in A–Z order.
- Example structure:
```python
"""Module docstring."""

__all__ = ['PublicClass', 'public_function']

# --- Public (top): classes first (A–Z), then functions (A–Z) ---

class PublicClass:
    ...

def public_function():
    ...

# --- Internal/private (bottom): alphabetically sorted ---

def _internal_helper():
    ...
```

#### Imports
- **Prefer imports at the top of the module** - Put `import` and `from ... import` statements at the top of the file whenever possible (after the module docstring, before `__all__` or code). Group in order: standard library, third-party, first-party/local.
- **Deferred imports** - Use imports inside functions or methods only when necessary to avoid circular imports or to defer loading a heavy/optional dependency until it is used.

#### Code Integrity and Agent Boundaries
- **Preserve behavior** - Do not change existing behavior unless the task explicitly asks for it. When fixing bugs, fix the implementation to match the intended (or documented) behavior; do not change tests or docstrings to match broken behavior.
- **Tests are the contract** - Do not relax, skip, or remove tests to make a change “pass”. Do not add `# pragma: no cover` or narrow test scope without a documented reason (e.g. platform-specific code).
- **Fix failing tests properly** - If your change causes test failures, fix the implementation so that existing test expectations remain valid, or update the tests only when the intended behavior has deliberately changed (and document why).
- **Safe to do without permission** - Reading files, running tests, running linters/type checks, and applying style fixes that match this document are expected. Prefer these to validate changes.
- **Prefer human approval for** - Adding or removing dependencies, changing CI/config that affects the whole repo, broad refactors, or deleting non-obsolete code. When in doubt, make the minimal change and note follow-ups.

### 3. Project Structure

```
src/
├── deda/                    # Main package
│   ├── app/                 # UI application code
│   │   ├── _app.py         # Application entry point
│   │   ├── _main_window.py # Main window
│   │   ├── _dialogs.py     # Dialog windows
│   │   └── icons/          # UI icons
│   ├── core/               # Core functionality
│   │   ├── _plugin.py      # Plugin system
│   │   ├── _config.py      # Configuration management
│   │   ├── _project.py     # Project management
│   │   ├── _types.py        # Type definitions
│   │   ├── finder/         # Application finders
│   │   ├── launcher/       # Application launchers
│   │   └── types/          # Data types
│   ├── plugins/            # Plugin implementations
│   │   ├── perforce/       # Perforce plugin
│   │   ├── jira/           # Jira plugin
│   │   ├── maya/           # Maya plugin
│   │   └── ...
│   └── log.py              # Logging setup
└── dedaverse/              # CLI entry point
    └── __main__.py         # Click CLI commands
```

### 4. Configuration System

The configuration uses a **layered approach**:
1. **Site Config** - System-wide settings (from `DEDAVERSE_SITE_CONFIG` env var)
2. **User Config** - User-specific settings (`~/.dedaverse/user.cfg`)
3. **Project Config** - Project-specific settings (`{project_root}/.dedaverse/project.cfg`)

**When working with config:**
- Use `LayeredConfig.instance()` to get the singleton
- Access via `config.user`, `config.current_project`, etc.
- Always validate before saving
- Use `ProjectConfig.load(path)` and `project.save()` for persistence

### 5. Plugin System

#### Plugin Types
- **Application** - DCC launchers (Maya, Houdini, etc.)
- **FileManager** - Version control (Perforce, filesystem)
- **TaskManager** - Task tracking (Jira)
- **Service** - Web services
- **Tool** - UI tools
- **NotificationSystem** - Notifications

#### Creating a Plugin
```python
from deda.core import Plugin, PluginRegistry

class MyPlugin(Plugin):
    def __init__(self, name, version=None, **kwargs):
        super().__init__(name, version=version, **kwargs)
    
    def load(self):
        """Initialize the plugin."""
        self._loaded = True
        return True

# Register the plugin
PluginRegistry().register(MyPlugin('MyPlugin', version='1.0.0'))
```

#### Plugin Loading
- Plugins are auto-discovered from `src/deda/plugins/` and `DEDAVERSE_PLUGIN_DIRS`
- Each plugin module should register itself on import
- Plugins are loaded after the main window is created

### 6. UI Development (PySide6)

#### Window Creation
- Inherit from appropriate Qt classes (`QMainWindow`, `QDialog`, `QWidget`)
- Use `get_top_window()` for parent windows
- Follow existing patterns in `_main_window.py` and `_dialogs.py`

#### Signals and Slots
- Use Qt signals for communication
- Example:
```python
class MyWidget(QtWidgets.QWidget):
    item_created = QtCore.Signal(object)
    
    def _on_item_created(self, item):
        self.item_created.emit(item)
```

#### Icons and Resources
- Store icons in `src/deda/app/icons/`
- Use `Path(__file__).parent / 'icons' / 'icon.png'` for paths
- Support both PNG and other formats as needed

### 7. Logging

#### Setup
- Use `deda.log.initialize(loglevel='DEBUG')` to initialize
- Get logger: `log = logging.getLogger(__name__)`
- Use coloredlogs for better output

#### Best Practices
- Use appropriate log levels
- Include context in messages
- Log exceptions with `log.exception()`
- Example:
```python
log = logging.getLogger(__name__)

log.debug(f'Loading plugin: {plugin_name}')
log.info(f'Plugin {plugin_name} loaded successfully')
log.warning(f'Plugin {plugin_name} has deprecated features')
log.error(f'Failed to load plugin {plugin_name}: {err}')
```

### 8. Data Classes

#### Configuration Classes
- Use `@dataclass_json` and `@dataclass` decorators
- Implement `__eq__` and `__hash__` properly
- **Important**: `__hash__` must use tuples: `hash((self.name, self.version))`
- Example:
```python
@dataclass_json
@dataclass(eq=False)
class AppConfig:
    name: str
    version: str
    
    def __eq__(self, other):
        return self.name == other.name and self.version == other.version
    
    def __hash__(self):
        return hash((self.name, self.version))  # ✅ Correct
```

### 9. Common Tasks

#### Adding a New Plugin
1. Create directory: `src/deda/plugins/my_plugin/`
2. Create `__init__.py` with plugin registration
3. Inherit from appropriate base class (`Application`, `FileManager`, etc.)
4. Implement required methods
5. Register in `__init__.py`:
```python
from deda.core import PluginRegistry, Application

class MyAppPlugin(Application):
    def __init__(self):
        super().__init__('MyApp', executable='myapp.exe')
    
    def find(self):
        # Find executable logic
        pass
    
    def load(self):
        self._loaded = True
        return True

PluginRegistry().register(MyAppPlugin())
```

#### Adding a New Dialog
1. Create class inheriting from `QtWidgets.QDialog`
2. Follow patterns in `_dialogs.py`
3. Use signals for communication
4. Handle parent window properly

#### Modifying Configuration
1. Understand the layer (Site/User/Project)
2. Load existing config: `config = LayeredConfig.instance()`
3. Modify properties
4. Save: `config.save()` or `project.save()`

### 10. Testing

#### When to Run Tests
- **Run pytest in the project venv whenever code changes are made.** After modifying source code, run the test suite to ensure nothing is broken.
- Use the project’s virtual environment: activate it, then run `pytest` (or `uv run pytest` / `python -m pytest tests/`).
- Optionally use pre-commit: with `pre-commit install`, pytest runs automatically on `git commit` (see [Pre-commit](#pre-commit) below).

#### Running Tests
```bash
# From repo root, with venv activated (or uv run):
python -m pytest tests/

# With coverage report (aim for 100% on covered code):
python -m pytest tests/ --cov=src/deda --cov-report=term-missing

# Exclude tests that require network (default run should not hit network):
python -m pytest tests/ -m "not network"
```

#### Security (bandit) and complexity (radon)
- **Bandit** runs in CI and pre-commit to scan `src/deda` for common security issues. Config: `[tool.bandit]` in `pyproject.toml` (excludes, skips). CI fails on high-severity findings; fix the code or add `# nosec <id>` with a brief justification where the risk is accepted.
- **Radon** runs in CI to report cyclomatic complexity (`radon cc`). Blocks with grade C or worse are reported; the step is informational (does not fail the job).
- **Local runs:**
  - Security: `bandit -r src/deda -c pyproject.toml -f screen`
  - Complexity: `radon cc src/deda -n C -a -s --total-average`
- CI produces coverage (pytest-cov), bandit JSON, and radon JSON; coverage and bandit/radon reports are uploaded as artifacts.

#### Import Unittests
- **Import tests** live in `tests/test_imports.py`. They verify that every public and internal module can be imported without error.
- When you add a new package or module under `src/deda`, add a corresponding import in `test_imports.py` (in the appropriate `test_import_*` method or in `test_imports()`).
- Run at least the import tests after structural or dependency changes: `python -m pytest tests/test_imports.py -v`.

#### No Network in Unit Tests
- **Unit tests must not hit network services** (no HTTP, no sockets, no external APIs). Tests must run offline and deterministically.
- Use **mocks or patches** for any code that would perform network I/O (e.g. `@patch('module.requests.get')`, `unittest.mock.Mock`).
- Tests that require real network access must be marked with `@pytest.mark.network` and excluded from the default run: `pytest -m "not network"`.

#### Coverage Goal
- **Aim for 100% test coverage** for code you add or change, excluding lines that are explicitly excluded (e.g. `pragma: no cover`, or platform-specific branches that are hard to exercise in CI).
- Coverage is reported in `htmlcov/` and via `--cov-report=term-missing`. Use it to find untested branches and add tests.

#### Test Structure
- Tests go in `tests/` directory.
- Use pytest-style tests; unittest-style (`unittest.TestCase`) is also supported (e.g. `test_imports.py`).
- Test imports, configuration, and core functionality; UI tests are optional (can be complex).

#### Test Patterns
- **Naming** — Prefer one test file per module: `tests/test_<module>.py`. Use classes to group related cases: `class TestFeatureName:`. Name test methods so that behavior and scenario are clear: `test_<behavior>_<scenario>` (e.g. `test_load_project_returns_none_when_missing`).
- **Fixtures** — Use `tmp_path` for any file or directory creation so tests are isolated and leave no artifacts. Use `@pytest.fixture` for shared setup (e.g. config, temp dirs). Prefer dependency injection in code so fixtures can supply fakes.
- **Mocking** — Unit tests must not call the network or external services. Use `unittest.mock.patch` (e.g. `@patch('module.requests.get')`) or `unittest.mock.Mock` for I/O, APIs, and optional dependencies. Patch at the use site (e.g. `patch('deda.core._config.requests.get')`), not at the definition.
- **Test data** — Keep test data minimal and next to the test or in `tests/` (e.g. `tests/data/`). Avoid hardcoded paths; use `tmp_path` or `Path(__file__).parent`.
- **Determinism** — Tests must be deterministic. No reliance on order of execution, system time (unless explicitly testing time behavior), or external state. Mark and exclude network-dependent tests with `@pytest.mark.network` and run default suite with `-m "not network"`.

#### Design for Testability
- **Write testable code** — Prefer pure functions and small, single-purpose functions. Prefer dependency injection over global state or module-level singletons where practical so that tests can inject mocks or fakes.
- **New code must be testable** — When adding a new module or public API, add or extend tests in the same change. Cover the main success path and at least one failure or edge case. Rely on import tests (`test_imports.py`) for structural changes.
- **Public API surface** — Ensure the public API (e.g. `deda.core`, plugin interfaces) is importable and key branches are covered by tests. Use `--cov=src/deda --cov-report=term-missing` to find gaps.

#### PySide6 Availability in Tests
- **PySide6 is always assumed to be available** in test files.
- **Do NOT** add try-except blocks to check for PySide6 availability.
- **Do NOT** use `@unittest.skipIf(not PYSIDE6_AVAILABLE, ...)` decorators.
- Simply import PySide6 directly: `from PySide6 import QtWidgets`
- If PySide6 is not available, the test should fail (this indicates a dependency issue that needs to be fixed).
- Example:
```python
import unittest
from PySide6 import QtWidgets  # ✅ Direct import, no try-except

class TestMyWidget(unittest.TestCase):
    def test_widget_creation(self):
        widget = QtWidgets.QWidget()
        self.assertIsNotNone(widget)
```

#### Pre-commit
- To run pytest automatically on every commit, install pre-commit and the repo hook:
  ```bash
  pip install pre-commit
  pre-commit install
  ```
- The hook runs `pytest tests/` (no network tests). See `.pre-commit-config.yaml` for the exact command.

### 11. Code Review Checklist

Before submitting code, ensure:
- [ ] Type hints added to all new functions
- [ ] No bare `except:` clauses
- [ ] Proper error handling with logging
- [ ] Paths use `pathlib.Path` (new code)
- [ ] Cross-platform compatibility considered
- [ ] Docstrings added to public methods
- [ ] Follows existing code style
- [ ] No hardcoded Windows paths (use platform detection)
- [ ] Resources properly managed (context managers)
- [ ] Configuration changes are validated
- [ ] Plugin registration follows patterns
- [ ] **pytest passes** in the project venv (`python -m pytest tests/`); unit tests do not hit the network
- [ ] **Code integrity** — Tests were not relaxed, skipped, or removed to make a change pass; failing tests were fixed by correcting the implementation (or by updating tests only when intended behavior changed)
- [ ] **Testability** — New or touched code has tests (or is covered by existing tests); new modules are listed in `tests/test_imports.py` where appropriate

### 12. Common Pitfalls to Avoid

#### ❌ Don't Do This:
```python
# Bare exception
except:
    pass

# Hardcoded paths
path = r'C:\Users\...'

# Missing type hints
def get_project(name):
    ...

# Incorrect hash
def __hash__(self):
    return hash(self.name, self.version)  # Wrong!

# Missing parameter
dcc_env = self.setup_env()  # Missing env parameter

# Weakening tests to make code "pass"
assert result is None  # was: assert result == expected  # Wrong if behavior should stay the same!
@pytest.mark.skip("flaky")  # Prefer fixing the test or the code
```

#### ✅ Do This Instead:
```python
# Specific exceptions
except (ImportError, ModuleNotFoundError) as err:
    log.error(f'Error: {err}')

# Pathlib
from pathlib import Path
path = Path.home() / '.dedaverse' / 'config.json'

# Type hints
def get_project(self, name: str) -> ProjectConfig | None:
    ...

# Correct hash
def __hash__(self):
    return hash((self.name, self.version))

# Correct parameter
dcc_env = self.setup_env(dcc_env)

# Fix implementation to satisfy tests; only change test when intended behavior changes
assert result == expected  # Keep assertion; fix the code under test if it regressed
```

### 13. Platform Compatibility

#### Windows-Specific Code
- **Detect platform** before using Windows-specific features
- Use `platform.system() == 'Windows'` checks
- Provide alternatives for other platforms when possible
- Example:
```python
import platform

if platform.system() == 'Windows':
    from pathlib import Path
    startup_dir = Path.home() / 'AppData' / 'Roaming' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
else:
    # Linux/Mac alternative
    startup_dir = Path.home() / '.config' / 'autostart'
```

### 14. Documentation

#### Docstrings
- Use Google or NumPy style docstrings
- **Add Args, Returns, and Raises sections to docstrings where appropriate.** When improving or writing docstrings, include these sections whenever the function or method has parameters, returns a value, or may raise exceptions.
- Example:
```python
def load_project(self, proj_name: str) -> ProjectConfig | None:
    """Load the ProjectConfig for the given project.
    
    Args:
        proj_name: The name of the project to load.
        
    Returns:
        ProjectConfig instance if found, None otherwise.
        
    Raises:
        ValueError: If project name is not in user config.
    """
    ...
```

### 15. Git Workflow

**When creating branches or pull requests, consult [BRANCHING_STRATEGY.md](BRANCHING_STRATEGY.md) for the full workflow.** That document defines the branch structure (feature/ and bugfix/ branches → dev → main), naming conventions, merge flow, and best practices.

#### Branch Naming
- **Feature branches** - For new features, enhancements, or development work
  - Format: `feature/descriptive-name`
  - Examples: `feature/plugin-name`, `feature/new-dialog`, `feature/usd-viewer-integration`
  
- **Bug branches** - For bugfixes targeting the main branch
  - Format: `bug/bug-description` or `fix/bug-description`
  - Examples: `bug/memory-leak-fix`, `fix/hash-implementation`, `bug/cross-platform-paths`
  
- **Improvement branches** - For code improvements and refactoring
  - Format: `improvements/description`
  - Examples: `improvements/critical-fixes`, `improvements/type-hints`, `improvements/code-cleanup`

#### Commit Messages
- Use clear, descriptive commit messages
- Reference issues if applicable
- Example: `fix: correct __hash__ implementation in AppConfig`

### 16. References

- **[docs/ASSET_METADATA_DESIGN.md](docs/ASSET_METADATA_DESIGN.md)** - Directory structure and USD metadata file layout for `.dedaverse` and asset content folders; keep agentic and manual code changes aligned with this design
- **BRANCHING_STRATEGY.md** - Git branching workflow; use this when creating branches and PRs
- **IMPROVEMENTS.md** - List of known issues and improvements
- **README.md** - Project overview and getting started
- **pyproject.toml** - Dependencies and project metadata

### 17. Quick Reference

#### Validation Commands
Run these from the repo root with the project venv activated (or `uv run`). Use them to validate changes before considering a task complete.
```bash
# Run full test suite (no network tests)
python -m pytest tests/ -m "not network"

# Run tests with coverage (find untested code)
python -m pytest tests/ -m "not network" --cov=src/deda --cov-report=term-missing

# Run only import tests (after adding/removing modules)
python -m pytest tests/test_imports.py -v

# Run a single test file or test
python -m pytest tests/test_imports.py -v
python -m pytest tests/test_imports.py::TestImports::test_import_deda_core -v

# Security scan (bandit)
bandit -r src/deda -c pyproject.toml -f screen

# Complexity report (radon; grade C and worse)
radon cc src/deda -n C -a -s --total-average
```

#### Common Imports
```python
import logging
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from PySide6 import QtWidgets, QtCore, QtGui
```

#### Common Patterns
```python
# Get logger
log = logging.getLogger(__name__)

# Get config
config = LayeredConfig.instance()

# Get project
project = config.current_project

# Path handling
icon_path = Path(__file__).parent / 'icons' / 'icon.png'

# Plugin registration
PluginRegistry().register(MyPlugin('Name', version='1.0.0'))
```

## 🚀 Quick Start for Agents

When asked to modify or add code:

1. **Read the relevant files** - Understand the existing code structure
2. **Check [docs/ASSET_METADATA_DESIGN.md](docs/ASSET_METADATA_DESIGN.md)** - When changing asset hierarchy, `.dedaverse` layout, USDA structure, or asset content paths
3. **Check BRANCHING_STRATEGY.md** - When creating branches or PRs, follow the documented workflow (feature/bugfix → dev → main)
4. **Check IMPROVEMENTS.md** - See if your change addresses a known issue
5. **Follow patterns** - Match existing code style and architecture
6. **Add type hints** - Always include type information
7. **Handle errors** - Use specific exceptions and proper logging
8. **Preserve code integrity** - Do not relax or remove tests to make a change pass; fix the implementation to satisfy existing tests (see [Code Integrity and Agent Boundaries](#code-integrity-and-agent-boundaries))
9. **Test imports** - Ensure new code can be imported; add imports to `tests/test_imports.py` for new modules
10. **Run pytest** - After making code changes, run pytest in the project venv: `python -m pytest tests/ -m "not network"` (see [Testing](#10-testing)). Unit tests must not hit the network; use mocks for I/O
11. **Add tests for new code** - New modules or public behavior should have tests in the same change; use [Test Patterns](#test-patterns) and [Design for Testability](#design-for-testability)
12. **Update docs** - Add/update docstrings as needed

## 📝 Notes

- The codebase is actively being improved - see IMPROVEMENTS.md for planned changes
- Some Windows-specific code exists but should be made cross-platform
- Plugin system is extensible - follow existing plugin patterns
- Configuration is layered - understand which layer to modify
- UI uses Qt/PySide6 - follow Qt best practices

---

**Last Updated:** 2025-01-24
**Python Version:** 3.12+
**Qt Version:** PySide6 6.6+
