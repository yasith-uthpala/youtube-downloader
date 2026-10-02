@echo off
title YouTube Downloader Pro - 1-Click Setup & Launch
cd /d "%~dp0"

echo ========================================================
echo       YouTube Downloader Pro - Easy 1-Click Setup
echo ========================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not detected on your system.
    echo Please install Python from https://www.python.org/downloads/
    echo (Make sure to check "Add Python to PATH" during installation)
    echo.
    pause
    exit /b
)

echo [1/3] Checking & Installing required packages...
python -m pip install -r requirements.txt --quiet --no-warn-script-location
if %errorlevel% neq 0 (
    echo Retrying package installation...
    python -m pip install yt-dlp imageio-ffmpeg customtkinter pillow
)

echo [2/3] Setting up Desktop Shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'YouTube Downloader Pro.lnk')); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"\"\"%~dp0YouTube Downloader (Desktop App).vbs\"\"\"'; $s.WorkingDirectory = '%~dp0'; $s.Save()" >nul 2>&1

echo [3/3] Launching YouTube Downloader Pro...
start "" "YouTube Downloader (Desktop App).vbs"

echo.
echo Setup Complete! Starting application...
timeout /t 2 >nul
exit
