import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
rows = conn.execute(
    "SELECT name, description FROM companies WHERE description IS NOT NULL AND description != '' ORDER BY name"
).fetchall()
print(f'Компаний с описанием: {len(rows)}')
for name, desc in rows:
    print(f'  {name}: {desc[:100]}')
conn.close()
