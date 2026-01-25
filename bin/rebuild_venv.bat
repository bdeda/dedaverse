@echo off
@rem Rebuild the virtual environment with all dependencies including USD Core
@rem This script will delete the existing venv and recreate it with all dependencies

setlocal enabledelayedexpansion

@rem Get the script directory (bin/)
set SCRIPT_DIR=%~dp0

@rem Determine which venv to rebuild (DEV or production)
set VENV_NAME=.venv_DEV
set VENV_PATH=%SCRIPT_DIR%..\%VENV_NAME%

if "%1"=="prod" (
    set VENV_NAME=.venv
    set VENV_PATH=%SCRIPT_DIR%..\%VENV_NAME%
)

echo ========================================
echo Rebuilding Virtual Environment
echo ========================================
echo.
echo Target: %VENV_NAME%
echo Path: %VENV_PATH%
echo.

@rem Ask for confirmation
set /p CONFIRM="This will delete the existing virtual environment. Continue? (y/N): "
if /i not "%CONFIRM%"=="y" (
    echo Cancelled.
    exit /b 0
)

@rem Remove existing venv if it exists
if exist "%VENV_PATH%" (
    echo Removing existing virtual environment...
    rmdir /s /q "%VENV_PATH%"
    if errorlevel 1 (
        echo Error: Failed to remove existing virtual environment.
        echo Please close any programs using the venv and try again.
        pause
        exit /b 1
    )
)

@rem Create new virtual environment
echo.
echo Creating new virtual environment...
call py -3.12 -m venv "%VENV_PATH%"
if errorlevel 1 (
    echo Error: Failed to create virtual environment.
    echo Please ensure Python 3.12 or higher is installed.
    pause
    exit /b 1
)

@rem Upgrade pip, setuptools, and wheel
echo.
echo Upgrading pip, setuptools, and wheel...
call "%VENV_PATH%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip.
    pause
    exit /b 1
)

@rem Check for OpenUSD installation
echo.
echo Checking for NVIDIA OpenUSD installation...
set USD_ROOT=%SCRIPT_DIR%..\usd_root
if not exist "!USD_ROOT!\bin\usdview.bat" (
    echo.
    echo OpenUSD not found at: !USD_ROOT!
    echo.
    set /p INSTALL_USD="Would you like to install NVIDIA OpenUSD now? (y/N): "
    if /i "!INSTALL_USD!"=="y" (
        call "%SCRIPT_DIR%install_openusd.bat"
        if errorlevel 1 (
            echo Warning: OpenUSD installation failed or was cancelled.
            echo You can install it later by running: bin\install_openusd.bat
        )
        @rem Re-check after installation attempt
        if exist "!USD_ROOT!\bin\usdview.bat" (
            echo OpenUSD installation detected.
            set USD_ROOT=%SCRIPT_DIR%..\usd_root
        )
    ) else (
        echo Skipping OpenUSD installation.
        echo You can install it later by running: bin\install_openusd.bat
    )
) else (
    echo OpenUSD found at: !USD_ROOT!
    echo.
    @rem Set up OpenUSD environment for this session
    if exist "!USD_ROOT!\bin" (
        set PATH=!USD_ROOT!\bin;%PATH%
        if exist "!USD_ROOT!\lib\python" (
            set PYTHONPATH=!USD_ROOT!\lib\python;%PYTHONPATH%
        )
    )
)

@rem Install Dedaverse with all dependencies
echo.
echo Installing Dedaverse and all dependencies...
if "%VENV_NAME%"==".venv_DEV" (
    call "%VENV_PATH%\Scripts\python.exe" -m pip install -e %SCRIPT_DIR%..
) else (
    call "%VENV_PATH%\Scripts\python.exe" -m pip install %SCRIPT_DIR%..
)

if errorlevel 1 (
    echo Error: Failed to install Dedaverse.
    pause
    exit /b 1
)

@rem Verify USD Core installation
echo.
echo Verifying USD Core installation...
call "%VENV_PATH%\Scripts\python.exe" -c "from pxr import Usd; print('USD Core is installed and importable')" 2>nul
if errorlevel 1 (
    echo Warning: USD Core import test failed.
    echo Attempting to install usd-core explicitly...
    call "%VENV_PATH%\Scripts\python.exe" -m pip install "usd-core>=25.11"
    if errorlevel 1 (
        echo Error: Failed to install USD Core.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
) else (
    echo USD Core verified successfully!
)

@rem Verify usdview is available
echo.
echo Verifying usdview availability...

@rem First try OpenUSD installation
if exist "!USD_ROOT!\bin\usdview.bat" (
    echo Testing OpenUSD usdview...
    "!USD_ROOT!\bin\usdview.bat" --help >nul 2>&1
    if not errorlevel 1 (
        echo OpenUSD usdview is available!
        goto :usd_verified
    )
)

@rem Try Python module approach
call "%VENV_PATH%\Scripts\python.exe" -m usdview --help >nul 2>&1
if not errorlevel 1 (
    echo usdview is available via Python module!
    goto :usd_verified
)

@rem Check if usdview command is in PATH
where usdview >nul 2>&1
if not errorlevel 1 (
    echo usdview is available in PATH!
    goto :usd_verified
)

echo Warning: usdview command may not be available.
echo.
echo If you installed OpenUSD, ensure the PATH is set correctly.
echo You may need to run: call bin\setup_openusd.bat
echo.
echo Alternatively, usd-core from PyPI may not include GUI components.
echo You can still use USD programmatically via Python.

:usd_verified

echo.
echo ========================================
echo Virtual Environment Rebuild Complete!
echo ========================================
echo.
echo To activate the virtual environment, run:
echo   %VENV_PATH%\Scripts\activate.bat
echo.
echo Or use the batch files:
if "%VENV_NAME%"==".venv_DEV" (
    echo   bin\dedaverse_DEV.bat
) else (
    echo   bin\dedaverse.bat
)
echo.
pause
