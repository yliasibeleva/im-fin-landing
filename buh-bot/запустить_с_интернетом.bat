@echo off
chcp 65001 > nul
title CRM Империя — интернет-доступ
pushd "%~dp0"
set PYTHONUTF8=1
echo ===  CRM + Cloudflare / Serveo Tunnel  ===
python -u запустить_с_интернетом.py
echo.
echo [Сервер остановлен. Закройте окно или нажмите любую клавишу.]
pause > nul
popd
