@echo off
@rem Download and install NVIDIA OpenUSD distribution
@rem This script downloads the full OpenUSD installer from NVIDIA and sets it up

setlocal enabledelayedexpansion

@rem Get the script directory (bin/)
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set USD_ROOT=%PROJECT_ROOT%\usd_root

echo ========================================
echo NVIDIA OpenUSD Installation
echo ========================================
echo.

@rem Check if OpenUSD is already installed
if exist "%USD_ROOT%\bin\usdview.bat" (
    echo OpenUSD appears to be already installed at: %USD_ROOT%
    set /p REINSTALL="Reinstall? (y/N): "
    if /i not "!REINSTALL!"=="y" (
        echo Using existing installation.
        goto :configure
    )
    echo Removing existing installation...
    rmdir /s /q "%USD_ROOT%"
)

@rem Determine download URL and version
@rem NVIDIA provides different versions - we'll try to get the latest Python 3.12 compatible version
echo.
echo ========================================
echo OpenUSD Download Instructions
echo ========================================
echo.
echo Please visit: https://developer.nvidia.com/usd
echo.
echo Download the appropriate version for your Python:
echo   - Python 3.12: USD 25.08 Windows x86_64 (or later)
echo   - Python 3.11: USD 25.05 Windows x86_64 (legacy)
echo.
echo The download is a large zip file (several GB, may take 10-30 minutes).
echo.
echo After downloading, you can either:
echo   1. Run this script again and provide the zip file path
echo   2. Manually extract to: %PROJECT_ROOT%\usd_root
echo.
set /p MANUAL_DOWNLOAD="Have you downloaded the OpenUSD zip file? (y/N): "
if /i not "!MANUAL_DOWNLOAD!"=="y" (
    echo.
    echo Opening NVIDIA OpenUSD download page in your browser...
    start https://developer.nvidia.com/usd
    echo.
    echo Please download OpenUSD and then run this script again.
    echo.
    pause
    exit /b 0
)

@rem Ask for the downloaded zip file location
echo.
set /p ZIP_FILE="Enter the full path to the downloaded OpenUSD zip file: "
if not exist "!ZIP_FILE!" (
    echo Error: File not found: !ZIP_FILE!
    pause
    exit /b 1
)

@rem Extract the zip file
echo.
echo Extracting OpenUSD (this may take several minutes)...
echo Target directory: %USD_ROOT%
echo.

@rem Create target directory
if not exist "%USD_ROOT%" mkdir "%USD_ROOT%"

@rem Use PowerShell to extract (handles large files better)
powershell -Command "Expand-Archive -Path '!ZIP_FILE!' -DestinationPath '%PROJECT_ROOT%' -Force"
if errorlevel 1 (
    echo Error: Failed to extract OpenUSD zip file.
    echo Please ensure you have enough disk space and the file is not corrupted.
    pause
    exit /b 1
)

@rem Find the extracted folder (NVIDIA zip files may have versioned folder names)
echo.
echo Locating extracted OpenUSD installation...
for /d %%D in ("%PROJECT_ROOT%\usd-*") do (
    if exist "%%D\bin\usdview.bat" (
        echo Found OpenUSD at: %%D
        if not "%%D"=="%USD_ROOT%" (
            echo Moving to standard location...
            move "%%D" "%USD_ROOT%" >nul 2>&1
            if errorlevel 1 (
                echo Moving failed, using found location...
                set USD_ROOT=%%D
            )
        )
        goto :found
    )
)

@rem Check if it's already in the right place
if exist "%USD_ROOT%\bin\usdview.bat" (
    goto :found
)

echo Error: Could not find OpenUSD installation after extraction.
echo Please check the extracted files and ensure usdview.bat exists.
pause
exit /b 1

:found
echo.
echo OpenUSD installation found at: %USD_ROOT%
echo.

:configure
@rem Create a script to set up OpenUSD environment
echo Creating OpenUSD environment setup script...
(
    echo @echo off
    echo @rem OpenUSD environment setup
    echo set USD_ROOT=%USD_ROOT%
    echo if exist "%%USD_ROOT%%\bin" (
    echo     set PATH=%%USD_ROOT%%\bin;%%PATH%%
    echo     set PYTHONPATH=%%USD_ROOT%%\lib\python;%%PYTHONPATH%%
    echo     set PXR_PLUGINPATH_NAME=%%USD_ROOT%%\plugin;%%PXR_PLUGINPATH_NAME%%
    echo )
) > "%SCRIPT_DIR%setup_openusd.bat"

echo.
echo ========================================
echo OpenUSD Installation Complete!
echo ========================================
echo.
echo Installation location: %USD_ROOT%
echo.
echo To use OpenUSD commands, run:
echo   call bin\setup_openusd.bat
echo.
echo Or they will be automatically configured when using:
echo   bin\usdview.bat
echo.
pause
