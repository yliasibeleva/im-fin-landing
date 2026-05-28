import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
row = conn.execute("SELECT sql FROM sqlite_master WHERE name='companies'").fetchone()
print(row[0])
print()
for r in conn.execute('PRAGMA table_info(companies)'):
    print(r)
conn.close()
