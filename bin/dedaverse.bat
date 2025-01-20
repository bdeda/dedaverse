@echo off
@rem The Dedaverse application installer and startup script
@rem RESTART_CODE = 1212333
@rem UPDATE_CODE = 1212444

:install
@rem if not exists "%~dp0..\.venv\Scripts\python.exe" (
    echo Installing...
    call py -3.11 -m venv "%~dp0..\.venv"
    call "%~dp0..\.venv\Scripts\python.exe" -m pip install %~dp0..

    call "%~dp0..\.venv\Scripts\python.exe" -m pip install --upgrade dedaverse
)

:run
call "%~dp0..\.venv\Scripts\python.exe" -m dedaverse run

if errorlevel 1212333 goto run
if errorlevel 1212444 goto install