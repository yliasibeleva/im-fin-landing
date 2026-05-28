@echo off
chcp 65001 >nul
cd /d "D:\РС\Визитка\buh-bot"
echo Запуск дашборда...
echo Открыть в браузере: http://localhost:8000
echo Логин: admin
start "" "http://localhost:8000"
python web_app.py
pause
