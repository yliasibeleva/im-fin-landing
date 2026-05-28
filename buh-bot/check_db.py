import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data_storage/buh_bot.db')
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Таблицы в БД:')
for t in tables:
    cnt = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {cnt} записей")

print()
print('--- Бухгалтеры ---')
for r in conn.execute("SELECT * FROM accountants").fetchall():
    print(dict(r))

print()
print('--- Компании (активные) ---')
for r in conn.execute("SELECT id, name, tax_system, org_type, accountant_id, is_active FROM companies WHERE is_active=1").fetchall():
    print(dict(r))

print()
print('--- Компании (все) ---')
total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
print(f"Всего: {total}")

conn.close()
