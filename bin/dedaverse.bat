@echo off
setlocal enabledelayedexpansion
@rem The Dedaverse application installer and startup script
@rem RESTART_CODE = 1212333
@rem UPDATE_CODE = 1212444
set VENV_DIRNAME=.venv

:install
if not exist "%~dp0..\%VENV_DIRNAME%\Scripts\python.exe" (
    echo Creating virtual environment...
    call py -3.13 -m venv "%~dp0..\%VENV_DIRNAME%"
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Upgrading pip...
call "%~dp0..\%VENV_DIRNAME%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip.
    pause
    exit /b 1
)

@rem Check for OpenUSD installation. A USD build only loads in the Python it was built for, so
@rem DEDAVERSE_USD_ROOT (if set) overrides USD_ROOT with a build that matches this venv's Python.
if defined DEDAVERSE_USD_ROOT set "USD_ROOT=%DEDAVERSE_USD_ROOT%"
if exist "%USD_ROOT%" (
    echo OpenUSD found at: %USD_ROOT%
    @rem Set up OpenUSD environment
    if exist "%USD_ROOT%\bin" (
        set "PATH=%USD_ROOT%\bin;%USD_ROOT%\lib;!PATH!"
        @rem Older builds install the Python modules in lib\python, newer ones in Lib\site-packages
        if exist "%USD_ROOT%\lib\python" (
            set "PYTHONPATH=%USD_ROOT%\lib\python;!PYTHONPATH!"
        ) else if exist "%USD_ROOT%\Lib\site-packages" (
            set "PYTHONPATH=%USD_ROOT%\Lib\site-packages;!PYTHONPATH!"
        )
    )
) else (
    echo Note: OpenUSD not found. You can install it with: bin\install_openusd.bat
)

echo Installing Dedaverse and dependencies...
call "%~dp0..\%VENV_DIRNAME%\Scripts\python.exe" -m pip install -e %~dp0..
if errorlevel 1 (
    echo Error: Failed to install Dedaverse.
    pause
    exit /b 1
)

echo.
echo Virtual environment setup complete!
echo.

:run
call "%~dp0..\%VENV_DIRNAME%\Scripts\python.exe" -m dedaverse run

if errorlevel 1212333 goto run
if errorlevel 1212444 goto install