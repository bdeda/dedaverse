@echo off
@rem The Dedaverse application installer and startup script
@rem RESTART_CODE = 1212333
@rem UPDATE_CODE = 1212444

:install
if not exist "%~dp0..\.venv\Scripts\python.exe" (
    echo Creating virtual environment...
    call py -3.12 -m venv "%~dp0..\.venv"
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Upgrading pip...
call "%~dp0..\.venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Error: Failed to upgrade pip.
    pause
    exit /b 1
)

@rem Check for OpenUSD installation
set USD_ROOT=%~dp0..\usd_root
if exist "%USD_ROOT%\bin\usdview.bat" (
    echo OpenUSD found at: %USD_ROOT%
    @rem Set up OpenUSD environment
    if exist "%USD_ROOT%\bin" (
        set PATH=%USD_ROOT%\bin;%PATH%
        set PYTHONPATH=%USD_ROOT%\lib\python;%PYTHONPATH%
    )
) else (
    echo Note: OpenUSD not found. You can install it with: bin\install_openusd.bat
)

echo Installing Dedaverse and dependencies...
call "%~dp0..\.venv\Scripts\python.exe" -m pip install %~dp0..
if errorlevel 1 (
    echo Error: Failed to install Dedaverse.
    pause
    exit /b 1
)

@rem Verify USD availability (either from OpenUSD or pip package)
echo Verifying USD installation...
call "%~dp0..\.venv\Scripts\python.exe" -c "from pxr import Usd; print('USD is available')" 2>nul
if errorlevel 1 (
    if exist "%USD_ROOT%\bin\usdview.bat" (
        echo Warning: USD import failed even though OpenUSD is installed.
        echo This may indicate a Python version mismatch.
    ) else (
        echo Warning: USD Core not found. Attempting to install usd-core from PyPI...
        call "%~dp0..\.venv\Scripts\python.exe" -m pip install "usd-core>=25.11"
    )
)

echo.
echo Virtual environment setup complete!
echo USD Core should now be available when the venv is activated.
echo.

:run
call "%~dp0..\.venv\Scripts\python.exe" -m dedaverse run

if errorlevel 1212333 goto run
if errorlevel 1212444 goto install