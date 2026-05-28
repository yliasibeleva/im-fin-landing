import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

missing = [
    (2,  'Андрианова Елена',  'Бухгалтер', '89057642797', None, '@alenalucky82', 1),
    (15, 'Штырева Анна',      'Бухгалтер', '89534145858', None, None,            1),
]

for row in missing:
    exists = conn.execute('SELECT id FROM accountants WHERE id=?', (row[0],)).fetchone()
    if exists:
        print(f'  id={row[0]} ({row[1]}) уже есть')
        continue
    conn.execute(
        'INSERT INTO accountants (id, name, position, phone, email, tg, is_remote) VALUES (?,?,?,?,?,?,?)',
        row
    )
    print(f'  Восстановлен: id={row[0]} {row[1]}')

conn.commit()

print('\n=== Итог: все бухгалтеры ===')
for r in conn.execute('SELECT id, name FROM accountants ORDER BY name'):
    print(f'  id={r[0]}: {r[1]}')

print('\n=== Итог: компании по бухгалтерам ===')
for r in conn.execute('''
    SELECT a.name, count(*) FROM companies c
    JOIN accountants a ON c.accountant_id=a.id
    WHERE c.is_active=1 GROUP BY c.accountant_id ORDER BY count(*) DESC
'''):
    print(f'  {r[1]:3d}  {r[0]}')

conn.close()
