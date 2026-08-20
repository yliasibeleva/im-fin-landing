"""
Комбинированный лаунчер:
 1. Убивает старые cloudflared и web_app
 2. Запускает cloudflared Quick Tunnel
 3. Ждёт URL → пишет в tunnel_url.txt (web_app.py читает его при старте)
 4. Запускает web_app.py
 5. Отправляет ссылки в Telegram
 6. Мониторит оба процесса — перезапускает при падении
 7. При смене URL (новый туннель) — перезапускает web_app.py
"""
import subprocess, re, time, os, sys, sqlite3, threading

BASE = os.path.dirname(os.path.abspath(__file__))
CF   = os.path.join(BASE, 'cloudflared.exe')
LOG  = os.path.join(BASE, 'tunnel.log')
URL_FILE = os.path.join(BASE, 'tunnel_url.txt')
DB   = os.path.join(BASE, 'data_storage', 'buh_bot.db')

# ── Telegram ────────────────────────────────────────────────────────────────

def _tg_credentials():
    try:
        sys.path.insert(0, BASE)
        import config
        token = getattr(config, 'TG_TOKEN', '') or getattr(config, 'TELEGRAM_TOKEN', '') or getattr(config, 'TELEGRAM_BOT_TOKEN', '')
        chat  = getattr(config, 'TG_CHAT',  '') or getattr(config, 'TELEGRAM_CHAT_ID', '')
        return token, chat
    except Exception:
        return '', ''

def send_telegram(url):
    try:
        import requests as req
        token, chat = _tg_credentials()
        if not (token and chat):
            print('[launcher] Telegram: нет TG_TOKEN/TG_CHAT в config.py')
            return
        conn = sqlite3.connect(DB)
        rows = conn.execute(
            "SELECT name, access_token FROM accountants "
            "WHERE access_token IS NOT NULL ORDER BY name"
        ).fetchall()
        conn.close()
        links = '\n'.join(f'• {r[0]}: {url}/portal/{r[1]}' for r in rows)
        msg = (
            f'🌐 <b>CRM запущена — доступ из интернета</b>\n'
            f'Адрес: <code>{url}</code>\n\n'
            f'<b>Ссылки бухгалтеров:</b>\n{links}'
        )
        req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat, 'text': msg, 'parse_mode': 'HTML'},
            timeout=15
        )
        print('[launcher] Telegram: отправлено ✓')
    except Exception as e:
        print(f'[launcher] Telegram ошибка: {e}')

# ── Cloudflare tunnel ────────────────────────────────────────────────────────

def _read_url_from_log():
    try:
        text = open(LOG, encoding='utf-8', errors='ignore').read()
        m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', text)
        if m:
            return m.group()
    except Exception:
        pass
    return None

def _start_cloudflared():
    """Запускает cloudflared и возвращает (proc, url)."""
    open(LOG, 'w').close()
    proc = subprocess.Popen(
        [CF, 'tunnel', '--url', 'http://localhost:8000'],
        stderr=open(LOG, 'w', encoding='utf-8'),
        stdout=subprocess.DEVNULL
    )
    print('[launcher] Туннель запущен, жду URL (до 45 сек)...')
    for _ in range(45):
        time.sleep(1)
        url = _read_url_from_log()
        if url:
            return proc, url
    proc.terminate()
    return None, None

def _write_url(url):
    with open(URL_FILE, 'w', encoding='utf-8') as f:
        f.write(url)

# ── Web server ───────────────────────────────────────────────────────────────

def _start_web():
    return subprocess.Popen(
        [sys.executable, 'web_app.py'],
        cwd=BASE
    )

# ── Kill helpers ─────────────────────────────────────────────────────────────

def _kill_old():
    subprocess.run(['taskkill', '/F', '/IM', 'cloudflared.exe'], capture_output=True)
    # Убить web_app.py на порту 8000
    try:
        out = subprocess.check_output(['netstat', '-ano'], text=True, encoding='cp866', errors='ignore')
        pids = set()
        for line in out.splitlines():
            if ':8000' in line and 'LISTENING' in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        for pid in pids:
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    except Exception:
        pass
    time.sleep(1)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print('[launcher] === Запуск CRM с интернет-доступом ===')

    if not os.path.exists(CF):
        sys.exit(f'[launcher] cloudflared.exe не найден: {CF}')

    _kill_old()

    # Первый запуск туннеля
    cf_proc, current_url = _start_cloudflared()
    if not current_url:
        sys.exit('[launcher] Не удалось получить URL туннеля. Проверьте интернет.')

    _write_url(current_url)
    print(f'[launcher] URL: {current_url}')

    # Запускаем web-сервер (читает tunnel_url.txt)
    web_proc = _start_web()
    print('[launcher] Сервер запущен')
    time.sleep(2)

    # Telegram в фоне (не блокируем)
    threading.Thread(target=send_telegram, args=(current_url,), daemon=True).start()

    print('[launcher] Мониторинг (Ctrl+C для остановки)...')
    try:
        while True:
            time.sleep(20)

            # Проверяем cloudflared
            if cf_proc.poll() is not None:
                print('[launcher] Туннель упал, перезапускаю...')
                cf_proc, new_url = _start_cloudflared()
                if new_url and new_url != current_url:
                    current_url = new_url
                    _write_url(current_url)
                    print(f'[launcher] Новый URL: {current_url}')
                    # Перезапускаем web для подхвата нового URL
                    if web_proc.poll() is None:
                        web_proc.terminate()
                        web_proc.wait(timeout=5)
                    web_proc = _start_web()
                    threading.Thread(target=send_telegram, args=(current_url,), daemon=True).start()

            # Проверяем web-сервер
            if web_proc.poll() is not None:
                print('[launcher] Сервер упал, перезапускаю...')
                web_proc = _start_web()

            # Проверяем, не сменился ли URL в логе (tunnel reconnect)
            new_url = _read_url_from_log()
            if new_url and new_url != current_url:
                current_url = new_url
                _write_url(current_url)
                print(f'[launcher] URL обновился: {current_url}')
                if web_proc.poll() is None:
                    web_proc.terminate()
                    web_proc.wait(timeout=5)
                web_proc = _start_web()
                threading.Thread(target=send_telegram, args=(current_url,), daemon=True).start()

    except KeyboardInterrupt:
        print('\n[launcher] Остановка...')
        web_proc.terminate()
        if cf_proc and cf_proc.poll() is None:
            cf_proc.terminate()
        try:
            open(URL_FILE, 'w').close()
        except Exception:
            pass
        print('[launcher] Готово.')

if __name__ == '__main__':
    main()
