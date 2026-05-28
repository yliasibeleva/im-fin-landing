import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

print('=== СХЕМА accountants ===')
row = conn.execute("SELECT sql FROM sqlite_master WHERE name='accountants'").fetchone()
print(row[0] if row else 'Таблица не найдена')

print('\n=== КОЛОНКИ ===')
for r in conn.execute('PRAGMA table_info(accountants)'):
    print(r)

print('\n=== FK в companies ===')
for r in conn.execute('PRAGMA foreign_key_list(companies)'):
    print(r)

print('\n=== Привязки бухгалтеров к компаниям ===')
for r in conn.execute('SELECT accountant_id, count(*) FROM companies WHERE accountant_id IS NOT NULL GROUP BY accountant_id'):
    name = conn.execute('SELECT name FROM accountants WHERE id=?', (r[0],)).fetchone()
    print(f'  id={r[0]} ({name[0] if name else "?"}): {r[1]} компаний')

print('\n=== Тест добавления (dry run) ===')
try:
    conn.execute('INSERT INTO accountants (name, position, phone, tg, is_remote) VALUES (?,?,?,?,?)',
                 ('Тест', None, None, None, 0))
    conn.rollback()
    print('INSERT — OK')
except Exception as e:
    print(f'INSERT ошибка: {e}')

print('\n=== Тест удаления первого бухгалтера (dry run) ===')
first = conn.execute('SELECT id, name FROM accountants LIMIT 1').fetchone()
if first:
    try:
        conn.execute('DELETE FROM accountants WHERE id=?', (first[0],))
        conn.rollback()
        print(f'DELETE id={first[0]} ({first[1]}) — OK')
    except Exception as e:
        print(f'DELETE ошибка: {e}')

conn.close()
