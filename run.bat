@echo off
title YouTube Downloader Pro
echo Starting YouTube Downloader Server...
cd /d "%~dp0"
start "" http://localhost:8000
python app.py
pause
