import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

print('=== accountant_id в компаниях ===')
rows = conn.execute('''
    SELECT c.accountant_id, a.name, count(*) as cnt
    FROM companies c
    LEFT JOIN accountants a ON c.accountant_id = a.id
    WHERE c.is_active=1
    GROUP BY c.accountant_id
    ORDER BY cnt DESC
''').fetchall()
for r in rows:
    print(f'  accountant_id={r[0]}  ({r[1] or "NULL"})  → {r[2]} компаний')

print('\n=== operator_id в компаниях ===')
rows2 = conn.execute('''
    SELECT c.operator_id, a.name, count(*) as cnt
    FROM companies c
    LEFT JOIN accountants a ON c.operator_id = a.id
    WHERE c.is_active=1
    GROUP BY c.operator_id
    ORDER BY cnt DESC
''').fetchall()
for r in rows2:
    print(f'  operator_id={r[0]}  ({r[1] or "NULL"})  → {r[2]} компаний')

conn.close()
