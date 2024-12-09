@echo off
@rem The Dedaverse application installer and startup script
@rem RESTART_CODE = 1212333

:run
call py -3.11 -m dedaverse run

if errorlevel 1212333 goto run