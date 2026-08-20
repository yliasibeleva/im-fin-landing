@echo off
chcp 65001 > nul
pushd "%~dp0"
echo ===  CRM + Cloudflare Tunnel  ===
python запустить_с_интернетом.py
pause
popd
