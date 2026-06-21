"""
Импорт задач и доп.работ из Excel (Задачи.xlsx) в БД CRM.
- Не-июльские задачи → status='done' (архив)
- Июльские задачи   → status='pending' (актуальные)
- Доп.работы        → INSERT, company_id по fuzzy-match; без совпадения — skip
"""

import sqlite3
import json
from datetime import datetime

DB_PATH    = 'D:/РС/Визитка/buh-bot/data_storage/buh_bot.db'
JSON_PATH  = 'D:/РС/Визитка/buh-bot/zadachi_dump.json'

ACCOUNTANT_MAP = {
    'Аверичева М.':    1,
    'Багрянцева Е.':   3,
    'Барышева Я.':     5,
    'Михеева М.':      6,
    'Сибилев Д.О.':    9,
    'Сибилева Ю.':    10,
    'Сопова Ю.':      11,
    'Стаханова Ю.':   12,
    'Строкачева О.':  13,
    'Харзеева С.':    14,
    'Щёголева Е.':    16,
    'Манько Е.':      17,
    'Селихова И.':    21,
    'Шалимова Л.':    22,
}


def get_accountant_id(name):
    return ACCOUNTANT_MAP.get((name or '').strip())


def normalize_co(name):
    if not name:
        return ''
    s = str(name).strip()
    for pfx in ('ООО ', 'ИП ', 'АО ', 'ИА ', 'ПАО '):
        if s.upper().startswith(pfx):
            s = s[len(pfx):].strip()
    return s.strip('"\'«» ').upper()


def build_company_lookup(db):
    rows = db.execute('SELECT id, name FROM companies').fetchall()
    lookup = {}
    for r in rows:
        lookup[normalize_co(r['name'])] = r['id']
    return lookup, {r['name'].upper(): r['id'] for r in rows}


def find_company_id(client, lookup, raw_lookup):
    if not client:
        return None
    norm = normalize_co(client)
    if norm in lookup:
        return lookup[norm]
    # substring match
    for key, cid in lookup.items():
        if norm and (norm in key or key in norm):
            return cid
    return None


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')

    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    co_lookup, co_raw = build_company_lookup(db)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ── Текущие задачи в БД: ключ (title, accountant_id, due_date) → id ──
    existing = {}
    for r in db.execute('SELECT id, title, accountant_id, due_date FROM tasks'):
        key = (
            (r['title'] or '').strip(),
            r['accountant_id'],
            r['due_date'],
        )
        existing[key] = r['id']

    # ══════════════════════════════════
    # ЗАДАЧИ
    # ══════════════════════════════════
    z = data['задачи']
    ins_tasks = 0
    upd_tasks = 0
    skip_tasks = 0

    for r in z[1:]:
        if not r or not r[2]:
            continue
        title = str(r[2]).strip()
        if not title:
            continue

        due_date      = str(r[4]) if r[4] else None
        acc_name      = str(r[5]).strip() if r[5] else None
        accountant_id = get_accountant_id(acc_name)
        client        = str(r[3]).strip() if r[3] else None
        note          = str(r[7]).strip() if len(r) > 7 and r[7] else None
        created_str   = str(r[1]) if r[1] else now[:10]

        is_july  = bool(due_date and due_date.startswith('2026-07'))
        status   = 'pending' if is_july else 'done'
        done_at  = None if is_july else now

        key = (title, accountant_id, due_date)
        if key in existing:
            task_id = existing[key]
            if task_id is None:
                # вставлено в этом же прогоне — пропустить
                skip_tasks += 1
                continue
            # Обновить статус если нужно
            row = db.execute(
                'SELECT status FROM tasks WHERE id=?', (task_id,)
            ).fetchone()
            if row and not is_july and row['status'] != 'done':
                db.execute(
                    'UPDATE tasks SET status=?, completed_at=? WHERE id=?',
                    ('done', now, task_id),
                )
                upd_tasks += 1
            else:
                skip_tasks += 1
            continue

        desc_parts = []
        if client:
            desc_parts.append(f'Клиент: {client}')
        if note:
            desc_parts.append(f'Примечание: {note}')
        description = ' | '.join(desc_parts) or None
        company_id  = find_company_id(client, co_lookup, co_raw)

        db.execute(
            '''INSERT INTO tasks
               (title, description, accountant_id, company_id,
                due_date, status, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (title, description, accountant_id, company_id,
             due_date, status, created_str, done_at),
        )
        existing[key] = None
        ins_tasks += 1

    db.commit()
    print(f'ЗАДАЧИ: вставлено {ins_tasks}, обновлено {upd_tasks}, пропущено {skip_tasks}')

    # ══════════════════════════════════
    # ДОП. РАБОТЫ
    # ══════════════════════════════════
    dop = data['доп. работы']
    ins_works   = 0
    skip_works  = 0
    no_company  = []

    for r in dop[1:]:
        if not r or not r[0] or isinstance(r[0], str):
            continue
        if not r[2]:
            continue

        work_date   = str(r[1]) if r[1] else None
        description = str(r[2]).strip()
        client      = str(r[3]).strip() if len(r) > 3 and r[3] else None
        acc_name    = str(r[4]).strip() if len(r) > 4 and r[4] else None

        if not work_date or not description:
            continue

        company_id    = find_company_id(client, co_lookup, co_raw)
        accountant_id = get_accountant_id(acc_name)

        if not company_id:
            no_company.append(client)
            skip_works += 1
            continue

        db.execute(
            '''INSERT INTO additional_works
               (company_id, accountant_id, description, work_type, work_date, hours, amount)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (company_id, accountant_id, description, 'Иное', work_date, 0, 0),
        )
        ins_works += 1

    db.commit()
    db.close()

    print(f'ДОП.РАБОТЫ: вставлено {ins_works}, пропущено (нет компании) {skip_works}')
    if no_company:
        uniq = sorted(set(no_company))
        print(f'  Не найдены компании ({len(uniq)} уникальных):')
        for c in uniq:
            print(f'    {c}')


if __name__ == '__main__':
    main()
