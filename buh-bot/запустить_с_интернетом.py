"""
Лаунчер с постоянным URL через serveo.net (SSH, без регистрации).
Если serveo не доступен — fallback на cloudflared Quick Tunnel.

URL всегда один: https://imperiacrm.serveo.net
(при первом запуске поддомен закрепляется за вашим SSH-ключом)
"""
import subprocess, re, time, os, sys, sqlite3, threading, socket

# UTF-8 вывод через переменную окружения (не reconfigure — он глушит flush)
os.environ.setdefault('PYTHONUTF8', '1')

BASE     = os.path.dirname(os.path.abspath(__file__))
CF       = os.path.join(BASE, 'cloudflared.exe')
CF_LOG   = os.path.join(BASE, 'tunnel.log')
URL_FILE = os.path.join(BASE, 'tunnel_url.txt')
DB       = os.path.join(BASE, 'data_storage', 'buh_bot.db')
PIDFILE  = os.path.join(BASE, 'launcher.pid')

SERVEO_SUBDOMAIN = 'imperiacrm'          # поддомен serveo — фиксированный
SERVEO_URL       = f'https://{SERVEO_SUBDOMAIN}.serveo.net'

# ── Telegram ────────────────────────────────────────────────────────────────

def _tg_creds():
    try:
        sys.path.insert(0, BASE)
        import config
        token = (getattr(config, 'BOT_TOKEN', '')
                 or getattr(config, 'TG_TOKEN', '')
                 or getattr(config, 'TELEGRAM_TOKEN', ''))
        # Чат: группа бухгалтеров → первый admin → env TG_CHAT
        chat = (getattr(config, 'ACCOUNTANTS_GROUP_ID', '') or '')
        if not chat:
            admin_ids = getattr(config, 'ADMIN_IDS', [])
            chat = admin_ids[0] if admin_ids else ''
        if not chat:
            chat = os.getenv('TG_CHAT', '')
        return token, chat
    except Exception:
        return '', ''

def send_telegram(url):
    try:
        import requests as req
        token, chat = _tg_creds()
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
            f'🌐 <b>CRM запущена</b>\n'
            f'Адрес: <code>{url}</code>\n\n'
            f'<b>Ссылки бухгалтеров:</b>\n{links}'
        )
        req.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat, 'text': msg, 'parse_mode': 'HTML'},
            timeout=15,
            proxies={}          # обходим системный SOCKS-прокси
        )
        print('[launcher] Telegram: отправлено ✓')
    except Exception as e:
        print(f'[launcher] Telegram ошибка: {e}')

# ── URL file ─────────────────────────────────────────────────────────────────

def _write_url(url):
    with open(URL_FILE, 'w', encoding='utf-8') as f:
        f.write(url)

# ── Web server ───────────────────────────────────────────────────────────────

def _start_web():
    return subprocess.Popen([sys.executable, 'web_app.py'], cwd=BASE)

# ── Kill old processes ────────────────────────────────────────────────────────

def _port_free(port=8000):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False

def _kill_old():
    # Убить предыдущий экземпляр лаунчера по PID-файлу
    if os.path.exists(PIDFILE):
        try:
            old_pid = int(open(PIDFILE).read().strip())
            subprocess.run(['taskkill', '/F', '/PID', str(old_pid)], capture_output=True)
            print(f'[launcher] Убит старый лаунчер PID={old_pid}')
        except Exception:
            pass

    # Записываем свой PID
    with open(PIDFILE, 'w') as f:
        f.write(str(os.getpid()))

    # Убить cloudflared и ssh-туннели
    subprocess.run(['taskkill', '/F', '/IM', 'cloudflared.exe'], capture_output=True)

    # Убить процесс на порту 8000
    try:
        out = subprocess.check_output(
            ['netstat', '-ano'], text=True, encoding='cp866', errors='ignore'
        )
        pids = set()
        for line in out.splitlines():
            if ':8000' in line and 'LISTENING' in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        for pid in pids:
            if pid != str(os.getpid()):
                subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
                print(f'[launcher] Убит процесс на порту 8000, PID={pid}')
    except Exception:
        pass

    # Ждём пока порт освободится (до 8 сек)
    for i in range(8):
        if _port_free():
            break
        time.sleep(1)
    else:
        print('[launcher] Предупреждение: порт 8000 всё ещё занят')

# ── SERVEO tunnel ─────────────────────────────────────────────────────────────

def start_serveo():
    """
    Запускает SSH-туннель на serveo.net.
    Возвращает (proc, url) или (None, None) при ошибке.
    """
    print(f'[launcher] Подключаю serveo.net → {SERVEO_URL} ...')
    proc = subprocess.Popen(
        [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'ExitOnForwardFailure=yes',
            '-R', f'{SERVEO_SUBDOMAIN}:80:localhost:8000',
            'serveo.net'
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )

    url = None
    deadline = time.time() + 20
    for line in proc.stdout:
        print(f'  {line.rstrip()}')
        if 'Forwarding HTTP' in line:
            # serveo даёт URL на serveousercontent.com (без регистрации)
            # или на imperiacrm.serveo.net (после регистрации SSH-ключа)
            m = re.search(r'https://[a-zA-Z0-9\-]+\.serveo(?:usercontent)?\.(?:net|com)', line)
            if m:
                url = m.group()
                break
        # Подсказка — ссылка для регистрации SSH-ключа (нужна 1 раз)
        if 'console.serveo.net/ssh/keys' in line:
            reg_url = re.search(r'https://\S+', line)
            if reg_url:
                print(f'[launcher] Для ПОСТОЯННОГО поддомена зарегистрируй SSH-ключ:')
                print(f'  {reg_url.group()}')
        if 'denied' in line.lower() or 'taken' in line.lower():
            print(f'[launcher] serveo: {line.rstrip()}')
            break
        if time.time() > deadline:
            break

    if url:
        return proc, url

    proc.terminate()
    return None, None

def monitor_serveo(proc, current_url_holder, web_holder):
    """Мониторит serveo-туннель и перезапускает если упал."""
    while True:
        time.sleep(15)
        if proc[0] and proc[0].poll() is not None:
            print('[launcher] serveo упал, перезапуск...')
            new_proc, new_url = start_serveo()
            if new_proc:
                proc[0] = new_proc
                if new_url and new_url != current_url_holder[0]:
                    current_url_holder[0] = new_url
                    _write_url(new_url)
                    if web_holder[0] and web_holder[0].poll() is None:
                        web_holder[0].terminate()
                        web_holder[0].wait(timeout=5)
                    web_holder[0] = _start_web()
                    threading.Thread(target=send_telegram, args=(new_url,), daemon=True).start()

# ── CLOUDFLARED fallback ───────────────────────────────────────────────────

def start_cloudflared():
    open(CF_LOG, 'w').close()
    proc = subprocess.Popen(
        [CF, 'tunnel', '--url', 'http://localhost:8000'],
        stderr=open(CF_LOG, 'w', encoding='utf-8'),
        stdout=subprocess.DEVNULL
    )
    print('[launcher] cloudflared запущен, жду URL (до 45 сек)...')
    for _ in range(45):
        time.sleep(1)
        try:
            text = open(CF_LOG, encoding='utf-8', errors='ignore').read()
            m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', text)
            if m:
                return proc, m.group()
        except Exception:
            pass
    proc.terminate()
    return None, None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 55)
    print('  CRM Империя PRO — запуск с интернет-доступом')
    print('=' * 55)

    _kill_old()

    # Пробуем serveo (стабильный URL)
    cf_proc_holder = [None]
    serveo_proc_holder = [None]

    serveo_proc, url = start_serveo()

    if serveo_proc and url:
        print(f'\n✓ Стабильный URL: {url}')
        serveo_proc_holder[0] = serveo_proc
    else:
        print('[launcher] serveo недоступен, переключаюсь на cloudflared...')
        if os.path.exists(CF):
            cf_proc, url = start_cloudflared()
            if cf_proc and url:
                cf_proc_holder[0] = cf_proc
                print(f'[launcher] cloudflared URL: {url}  (изменится при рестарте)')
            else:
                sys.exit('[launcher] Не удалось запустить ни один туннель.')
        else:
            sys.exit(f'[launcher] cloudflared.exe не найден: {CF}')

    _write_url(url)

    # Запускаем web-сервер
    web_holder = [_start_web()]
    print('[launcher] Сервер запущен')
    time.sleep(2)

    # Telegram в фоне
    threading.Thread(target=send_telegram, args=(url,), daemon=True).start()

    current_url_holder = [url]

    # Мониторинг serveo в отдельном потоке
    if serveo_proc_holder[0]:
        threading.Thread(
            target=monitor_serveo,
            args=(serveo_proc_holder, current_url_holder, web_holder),
            daemon=True
        ).start()

    print(f'\n[launcher] Мониторинг запущен. Ctrl+C для остановки.')
    print(f'[launcher] Адрес: {url}\n')

    try:
        while True:
            time.sleep(20)
            # Перезапускаем web если упал
            if web_holder[0] and web_holder[0].poll() is not None:
                print('[launcher] Сервер упал, перезапускаю...')
                web_holder[0] = _start_web()

            # Проверка cloudflared (если используется)
            if cf_proc_holder[0] and cf_proc_holder[0].poll() is not None:
                print('[launcher] cloudflared упал, перезапускаю...')
                cf_proc, new_url = start_cloudflared()
                if cf_proc:
                    cf_proc_holder[0] = cf_proc
                    if new_url and new_url != current_url_holder[0]:
                        current_url_holder[0] = new_url
                        _write_url(new_url)
                        if web_holder[0] and web_holder[0].poll() is None:
                            web_holder[0].terminate()
                            web_holder[0].wait(timeout=5)
                        web_holder[0] = _start_web()
                        threading.Thread(
                            target=send_telegram, args=(new_url,), daemon=True
                        ).start()

    except KeyboardInterrupt:
        print('\n[launcher] Остановка...')
        if web_holder[0] and web_holder[0].poll() is None:
            web_holder[0].terminate()
        if serveo_proc_holder[0] and serveo_proc_holder[0].poll() is None:
            serveo_proc_holder[0].terminate()
        if cf_proc_holder[0] and cf_proc_holder[0].poll() is None:
            cf_proc_holder[0].terminate()
        try:
            open(URL_FILE, 'w').close()
        except Exception:
            pass
        print('[launcher] Готово.')

if __name__ == '__main__':
    main()
