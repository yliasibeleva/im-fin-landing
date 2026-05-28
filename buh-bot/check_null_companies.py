import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
rows = conn.execute(
    "SELECT id, name FROM companies WHERE accountant_id IS NULL AND is_active=1 ORDER BY name"
).fetchall()
print(f'Компаний без бухгалтера: {len(rows)}')
for r in rows:
    print(f'  [{r[0]}] {r[1]}')
conn.close()
