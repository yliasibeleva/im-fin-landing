"""
Импорт описаний компаний из docx-карточек.
Запуск: python import_descriptions.py          — показать совпадения
        python import_descriptions.py --write   — записать в БД
"""
import sys, re, sqlite3, zipfile, io, os

sys.stdout.reconfigure(encoding='utf-8')

CARDS_DIR = r'\\imperfin-1c\share\Карточки предприятий\Готово'
DB_PATH   = 'data_storage/buh_bot.db'
WRITE     = '--write' in sys.argv


# ── Чтение docx ──────────────────────────────────────────────────────────────

def read_docx_text(path: str) -> str:
    """Извлекает весь текст из docx без сторонних библиотек."""
    with open(path, 'rb') as f:
        data = f.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        with z.open('word/document.xml') as xml_file:
            xml = xml_file.read().decode('utf-8')
    text = re.sub(r'<[^>]+>', ' ', xml)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Нормализация имён ─────────────────────────────────────────────────────────

ORG_PREFIXES = re.compile(
    r'^(ООО|ЗАО|ПАО|АО|ИП|АНО|НПО|НКО|ГКФХ|КФХ|ТСЖ|СНТ|ГК)\s+',
    re.IGNORECASE
)

# Ручные сопоставления: нормализованное имя из файла → id в БД
MANUAL_MAP = {
    'джеммарко':         35,   # файл Джеммарко → БД ДЖЕММАРКА
    'ададурова ег':       5,   # Adadurova E (латиница в БД)
    'астохова ла':       13,   # опечатка: Астохова → Астахова
    'райсингер ва':      29,   # Райсингер → Райссингер
    'аркада новая':      11,   # Аркада новая → АРКАДА
    'виолета':           22,   # Виолета → Виолетта
    'сибвей':            75,   # СИБВЕЙ → СИБВЭЙ
    'щитова лв':         98,   # опечатка: Щитова → Шитова
}


def normalize(s: str) -> str:
    """Убирает оргформу, точки/запятые, приводит к нижнему регистру; сливает инициалы."""
    s = ORG_PREFIXES.sub('', s.strip())
    s = re.sub(r'[.,\-—–]+', ' ', s).strip().lower()
    # Сливаем одиночные буквы-инициалы: "А В" → "ав", "А А" → "аа"
    s = re.sub(r'\b([а-яёa-z])\s+([а-яёa-z])\b', r'\1\2', s)
    s = re.sub(r'\b([а-яёa-z]{2})\s+([а-яёa-z])\b', r'\1\2', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_file_name(filename: str) -> str:
    """'Карточка предприятия ИП Антонов В.В..docx' → 'Антонов В.В.'"""
    name = filename
    name = re.sub(r'\.docx$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^Карточка\s+пред[а-я]+\s*', '', name, flags=re.IGNORECASE)
    name = name.strip('— ').strip()
    return name


# ── Нечёткое сопоставление ────────────────────────────────────────────────────

def score(db_name: str, file_name: str) -> int:
    """Возвращает очки совпадения (0 = нет совпадения)."""
    dn = normalize(db_name)
    fn = normalize(file_name)

    # Точное совпадение нормализованных строк
    if dn == fn:
        return 100

    dn_words = dn.split()
    fn_words = fn.split()

    if not dn_words or not fn_words:
        return 0

    # Первое слово совпадает (фамилия)
    if dn_words[0] == fn_words[0]:
        pts = 60
        # Второе слово тоже
        if len(dn_words) > 1 and len(fn_words) > 1:
            dw2 = re.sub(r'[^а-яёa-z]', '', dn_words[1])
            fw2 = re.sub(r'[^а-яёa-z]', '', fn_words[1])
            if dw2 and fw2 and (dw2.startswith(fw2) or fw2.startswith(dw2)):
                pts += 30
        return pts

    # Одно из слов файла содержится в названии БД (для многословных)
    for fw in fn_words[:3]:
        if len(fw) >= 4 and fw in dn:
            return 40

    # Начало первого слова (минимум 4 символа)
    if len(dn_words[0]) >= 4 and len(fn_words[0]) >= 4:
        common = min(len(dn_words[0]), len(fn_words[0]))
        if dn_words[0][:common] == fn_words[0][:common]:
            return 35

    return 0


def best_match(file_name: str, companies: list[tuple]) -> tuple | None:
    """Возвращает (id, name, score) лучшего совпадения или None."""
    results = [(cid, cname, score(cname, file_name)) for cid, cname in companies]
    results = [r for r in results if r[2] > 0]
    if not results:
        return None
    results.sort(key=lambda x: -x[2])
    best = results[0]
    # Есть конкурент с тем же счётом → неоднозначность
    if len(results) > 1 and results[1][2] == best[2]:
        return None
    return best


# ── Основной цикл ─────────────────────────────────────────────────────────────

conn = sqlite3.connect(DB_PATH)
companies = conn.execute(
    'SELECT id, name FROM companies WHERE is_active=1'
).fetchall()

files = [f for f in os.listdir(CARDS_DIR) if f.lower().endswith('.docx')]

matched   = []
unmatched = []

for filename in sorted(files):
    file_path = os.path.join(CARDS_DIR, filename)
    file_name = extract_file_name(filename)
    norm = normalize(file_name)

    # Сначала пробуем ручное сопоставление
    if norm in MANUAL_MAP:
        cid = MANUAL_MAP[norm]
        row = next((r for r in companies if r[0] == cid), None)
        cname = row[1] if row else f'id={cid}'
        text = read_docx_text(file_path)
        matched.append((cid, cname, file_name, 'ручное', text))
        continue

    result = best_match(file_name, companies)
    if result:
        cid, cname, pts = result
        text = read_docx_text(file_path)
        matched.append((cid, cname, file_name, pts, text))
    else:
        unmatched.append(file_name)

print(f'\n{"="*60}')
print(f'Карточек:   {len(files)}')
print(f'Совпало:    {len(matched)}')
print(f'Не найдено: {len(unmatched)}')
print(f'{"="*60}\n')

print('СОВПАДЕНИЯ:')
for cid, cname, fname, pts, text in matched:
    pts_str = f'{pts:3d}' if isinstance(pts, int) else f'{pts:>6}'
    print(f'  [{pts_str}] «{fname}» → БД: «{cname}» (id={cid})')

if unmatched:
    print('\nНЕ НАЙДЕНО (нужно вручную):')
    for name in unmatched:
        print(f'  - {name}')

if WRITE:
    print('\nЗапись в БД...')
    cur = conn.cursor()
    updated = 0
    for cid, cname, fname, pts, text in matched:
        cur.execute(
            'UPDATE companies SET description=? WHERE id=?',
            (text, cid)
        )
        updated += 1
    conn.commit()
    print(f'Обновлено {updated} компаний.')
else:
    print('\nДля записи запустите: python import_descriptions.py --write')

conn.close()
