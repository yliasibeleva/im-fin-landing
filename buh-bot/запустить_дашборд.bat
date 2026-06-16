@echo off
chcp 65001 >nul
pushd "%~dp0"
echo ===========================================
echo  Империя PRO - Дашборд
echo  Не закрывайте это окно!
echo ===========================================
echo.
echo Запуск сервера..
start "" "http://localhost:8000"
:loop
python web_app.py
echo.
echo Сервер остановлен. Перезапуск через 5 секунд..
timeout /t 5 >nul
goto loop
