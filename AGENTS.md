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

#### Test Structure
- Tests go in `tests/` directory
- Use pytest-style tests
- Test imports, configuration, and core functionality
- UI tests are optional (can be complex)

#### Running Tests
```bash
python -m pytest tests/
```

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
- Include Args, Returns, Raises sections
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

#### Branch Naming
- Use descriptive branch names: `feature/plugin-name`, `fix/bug-description`
- For improvements: `improvements/critical-fixes`

#### Commit Messages
- Use clear, descriptive commit messages
- Reference issues if applicable
- Example: `fix: correct __hash__ implementation in AppConfig`

### 16. References

- **IMPROVEMENTS.md** - List of known issues and improvements
- **README.md** - Project overview and getting started
- **pyproject.toml** - Dependencies and project metadata

### 17. Quick Reference

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
2. **Check IMPROVEMENTS.md** - See if your change addresses a known issue
3. **Follow patterns** - Match existing code style and architecture
4. **Add type hints** - Always include type information
5. **Handle errors** - Use specific exceptions and proper logging
6. **Test imports** - Ensure new code can be imported
7. **Update docs** - Add/update docstrings as needed

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
