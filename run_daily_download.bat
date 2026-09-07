@echo off
REM Daily automated data collection - triggered by Windows Task Scheduler.
REM Can also be double-clicked manually to run/verify on demand.
REM Output is appended to download_log.txt for inspection.

cd /d "%~dp0"
"venv\Scripts\python.exe" downloaders\download_all.py >> download_log.txt 2>&1
