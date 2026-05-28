import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

# Что реально в accountant_id
print('=== Значения accountant_id ===')
for r in conn.execute('SELECT accountant_id, count(*) FROM companies WHERE is_active=1 GROUP BY accountant_id ORDER BY count(*) DESC'):
    exists = conn.execute('SELECT name FROM accountants WHERE id=?', (r[0],)).fetchone() if r[0] else None
    print(f'  accountant_id={r[0]}  cnt={r[1]}  в таблице: {exists[0] if exists else "НЕТ"}')

# Выборочно — Антонов
r = conn.execute('SELECT id, name, accountant_id FROM companies WHERE name="Антонов"').fetchone()
print(f'\nАнтонов: id={r[0]}, accountant_id={r[1] if r else "не найден"}')
conn.close()
