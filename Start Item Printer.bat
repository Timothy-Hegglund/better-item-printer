@echo off
cd /d "%~dp0"
title Better Item Printer
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py
) else (
  python server.py
)
if errorlevel 1 echo Could not start. Install Python 3 from python.org if Python was not found.
pause
