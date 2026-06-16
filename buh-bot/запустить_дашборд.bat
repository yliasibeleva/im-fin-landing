@echo off
chcp 65001 >nul
pushd "%~dp0"
:loop
echo.
echo ===========================================
echo  Империя Финанс - Дашборд запущен
echo  Не закрывайте это окно!
echo ===========================================
echo.
start "" "http://localhost:8000"
python web_app.py
echo.
echo Сервер остановлен. Перезапуск через 5 секунд..
timeout /t 5 >nul
goto loop
