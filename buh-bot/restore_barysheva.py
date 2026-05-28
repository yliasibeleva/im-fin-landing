"""
Восстанавливает Барышеву Яну (id=5) и переназначает компании.
Запускать ОДИН раз.
"""
import json, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data_storage/buh_bot.db')

# Восстанавливаем Барышеву с теми же данными из accountants_data.json
# Сначала проверяем, не восстановлена ли уже
row = conn.execute('SELECT id FROM accountants WHERE id=5').fetchone()
if row:
    print('Барышева уже есть в базе, ничего не делаем.')
    conn.close()
    sys.exit(0)

# Вставляем с явным id=5
conn.execute(
    'INSERT INTO accountants (id, name, position, phone, email, tg, is_remote) VALUES (?,?,?,?,?,?,?)',
    (5, 'Барышева Яна', 'Бухгалтер', '89803626857', None, None, 0)
)
print('Барышева Яна (id=5) восстановлена.')

# Смотрим сколько компаний без бухгалтера
null_companies = conn.execute(
    'SELECT id, name FROM companies WHERE accountant_id IS NULL AND is_active=1 ORDER BY name'
).fetchall()
print(f'\nКомпаний без бухгалтера: {len(null_companies)}')
print('Их нужно вручную переназначить в дашборде.')
print('\nСписок компаний без бухгалтера:')
for c in null_companies:
    print(f'  id={c[0]}: {c[1]}')

conn.commit()
conn.close()
