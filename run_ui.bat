@echo off
cd /d "%~dp0"
echo Starting NetSage AI...
start "NetSage AI" cmd /k python src\server.py
ping 127.0.0.1 -n 2 >nul
start "" http://127.0.0.1:8000
