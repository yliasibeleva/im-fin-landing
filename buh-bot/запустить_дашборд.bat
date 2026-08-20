@echo off
chcp 65001 >nul
pushd "%~dp0"
title IMPERIA PRO
python _get_tokens.py
start "Tunnel" /min python tunnel_monitor.py
timeout /t 3 >nul
start "" "http://localhost:8000"
:server_loop
python web_app.py
timeout /t 5 >nul
goto server_loop
