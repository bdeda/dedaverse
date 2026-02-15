# Dedaverse Installation Guide

This guide walks you through installing Python 3.12, OpenUSD (with usdview), and Dedaverse so you can run the application and optionally the built-in USD viewer.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Install Python 3.12](#2-install-python-312)
3. [Install OpenUSD with usdview (optional but recommended)](#3-install-openusd-with-usdview-optional-but-recommended)
4. [Install Dedaverse](#4-install-dedaverse)
5. [First-time configuration](#5-first-time-configuration)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Prerequisites

- **Operating system:** Windows 10/11, macOS, or Linux (Ubuntu 20.04+ or equivalent).
- **Disk space:** Reserve at least 2–5 GB for Python, OpenUSD (if built), and Dedaverse dependencies (including PySide6 and USD).
- **Permissions:** Ability to install software and, on Windows, to run the Python installer with “Add Python to PATH” enabled.

---

## 2. Install Python 3.12

Dedaverse requires **Python 3.12 or newer** (3.13 is supported).

### Windows

1. Open [python.org/downloads](https://www.python.org/downloads/) and download **Python 3.12** (or 3.13) for Windows.
2. Run the installer.
3. **Important:** On the first screen, check **“Add python.exe to PATH”**, then click **“Install Now”** (or choose a custom install and ensure “Add Python to PATH” is selected).
4. Close and reopen any Command Prompt or PowerShell window.
5. Verify:
   ```bat
   py --list
   ```
   You should see 3.12 (or 3.13) listed. Then:
   ```bat
   py -3.12 -c "print('OK')"
   ```

### macOS

1. Install Python 3.12 via [python.org](https://www.python.org/downloads/) or Homebrew:
   ```bash
   brew install python@3.12
   ```
2. Ensure `python3.12` and `pip` are on your PATH (Homebrew usually adds this).
3. Verify:
   ```bash
   python3.12 --version
   ```

### Linux (e.g. Ubuntu)

1. Install Python 3.12 and venv:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
   ```
2. Verify:
   ```bash
   python3.12 --version
   ```

---

## 3. Install OpenUSD with usdview (optional but recommended)

The **Dedaverse built-in viewer** and the standalone **usdview** tool need OpenUSD built with **imaging** and **Usdviewq** (Qt). The `usd-core` package from PyPI does **not** include these; it only provides the core USD library. For full viewer support and usdview, use one of the options below.

### Option A: Build OpenUSD from source (full control)

This gives you OpenUSD with imaging and usdview in a dedicated directory. You will then use this Python (or a venv that uses it) when installing Dedaverse.

1. **Install build dependencies**
   - **Windows:** Install [Visual Studio](https://visualstudio.microsoft.com/) (Build Tools for Visual Studio) with “Desktop development with C++”. Install [CMake](https://cmake.org/download/) and add it to PATH.
   - **macOS:** Xcode Command Line Tools, CMake, Homebrew for dependencies (see [OpenUSD BUILDING.md](https://github.com/PixarAnimationStudios/OpenUSD/blob/main/BUILDING.md)).
   - **Linux:** Compiler, CMake, and the libraries listed in OpenUSD’s [BUILDING.md](https://github.com/PixarAnimationStudios/OpenUSD/blob/main/BUILDING.md) (e.g. OpenSubdiv for imaging).

2. **Clone and build OpenUSD**
   ```bash
   git clone https://github.com/PixarAnimationStudios/OpenUSD
   cd OpenUSD
   ```
   Then run the build script (adjust the install path to your preference):
   - **Linux / macOS:**
     ```bash
     python build_scripts/build_usd.py /path/to/USD
     ```
   - **Windows (Command Prompt):**
     ```bat
     python build_scripts\build_usd.py C:\USD
     ```
   The script will download dependencies, build USD core and imaging, and install into the given directory. This can take a long time.

3. **Use the built OpenUSD’s Python for Dedaverse**
   - The install directory will contain a `bin` (or `Scripts` on Windows) and `lib/python` (or similar). You can create a virtual environment that uses this Python, or activate the environment that the build provides (if any), and then install Dedaverse there (see [Section 4](#4-install-dedaverse)).

### Option B: Use PyPI usd-core only (no viewer / no usdview)

If you do **not** need the built-in viewer or usdview:

- You can skip building OpenUSD. Running `pip install dedaverse` will pull in **usd-core** from PyPI, which is enough for the main Dedaverse app (project/asset metadata, panels, plugins). The in-app USD viewer and usdview will not work until OpenUSD is installed with imaging and Usdviewq (Option A or a prebuilt package).

---

## 4. Install Dedaverse

Use a **virtual environment** so Dedaverse and its dependencies are isolated.

### Windows

1. Create a folder and venv (use a path without spaces if possible):
   ```bat
   mkdir D:\dedaverse_app
   py -3.12 -m venv D:\dedaverse_app\.venv
   ```

2. Activate the venv:
   ```bat
   D:\dedaverse_app\.venv\Scripts\activate
   ```

3. Upgrade pip and install Dedaverse:
   ```bat
   python -m pip install --upgrade pip
   pip install git+https://github.com/bdeda/dedaverse.git
   ```
   Or, from a local clone:
   ```bat
   cd path\to\dedaverse
   pip install -e .
   ```

4. Verify:
   ```bat
   dedaverse --help
   ```

### macOS / Linux

1. Create a folder and venv:
   ```bash
   mkdir -p ~/dedaverse_app
   python3.12 -m venv ~/dedaverse_app/.venv
   ```

2. Activate the venv:
   ```bash
   source ~/dedaverse_app/.venv/bin/activate
   ```

3. Upgrade pip and install Dedaverse:
   ```bash
   python -m pip install --upgrade pip
   pip install git+https://github.com/bdeda/dedaverse.git
   ```
   Or, from a local clone:
   ```bash
   cd path/to/dedaverse
   pip install -e .
   ```

4. Verify:
   ```bash
   dedaverse --help
   ```

### If you built OpenUSD (Option A)

- Activate the environment that uses the OpenUSD Python (or a venv that points to it), then run the same `pip install` steps above so Dedaverse and its dependencies (including PySide6) use that Python and can load Usdviewq.

---

## 5. First-time configuration

1. **Start Dedaverse**
   - From the activated venv:
     ```bat
     dedaverse
     ```
     (Windows) or `dedaverse` (macOS/Linux).
   - Or, on Windows, after installing the tray helper (see below), use the system-tray icon.

2. **Create or open a project**
   - Use the UI to create a new project (choose a project root directory and name) or open an existing one. Project metadata is stored under `{project_root}/.dedaverse/`.

3. **Optional: System tray and startup (Windows)**
   - To have Dedaverse start with Windows and show a tray icon:
     ```bat
     D:\dedaverse_app\.venv\Scripts\python.exe -m dedaverse install
     ```
   - Use the tray icon to open the app or adjust settings.

4. **Optional: Run the standalone viewer**
   - If OpenUSD was built with usdview:
     - **Linux/macOS:** `usdview path/to/file.usda` (using the OpenUSD install’s `bin` or your activated env).
     - **Windows:** Run `usdview` from the OpenUSD install’s `Scripts` or the env that has it.

---

## 6. Troubleshooting

| Issue | What to try |
|-------|-------------|
| `py` or `python3.12` not found | Reinstall Python and enable “Add to PATH”. Restart the terminal. On Linux, install `python3.12` and `python3.12-venv`. |
| `No module named 'deda'` or `dedaverse` | Activate the same venv you used for `pip install`, or reinstall: `pip install -e .` from the Dedaverse repo. |
| Viewer does not open or “No module named 'Usdviewq'” | The built-in viewer needs OpenUSD built with imaging and Usdviewq (see [Section 3](#3-install-openusd-with-usdview-optional-but-recommended)). Using only `usd-core` from PyPI is not enough for the viewer. |
| usdview not found | Install or build OpenUSD with usdview (Option A), then run `usdview` from that OpenUSD environment. |
| PySide6 / Qt errors on Linux | Install recommended system libraries (e.g. libxcb, libegl1, libgl1). See the project’s CI workflow or Qt docs for the full list. |
| Permission or path errors | Use a project root path you can write to; avoid paths with special characters or very long names. |

For more on the app and workflows, see [README.md](README.md). For development and code layout, see [AGENTS.md](AGENTS.md).
