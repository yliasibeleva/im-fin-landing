import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

# Штырева Анна = id=15
SHTYREV = 15
# Андрианова Елена = id=2
ANDRIANOVA = 2

shtyrev_ids = [5,10,9,8,13,19,20,23,27,33,47,50,54,52,68,73,80,83,84,87,93,94,95,102,103,104,105]
andrianova_ids = [24,26,59,70]
# Без бухгалтера: 66 (Пугачева Е), 30 (ГОЛД СЕТ?), 35 (ДЖЕММАРКА?), 106, 107
# ГОЛД СЕТ и ДЖЕММАРКА из импорта были Штырева
shtyrev_ids += [30, 35]

for cid in shtyrev_ids:
    conn.execute('UPDATE companies SET accountant_id=? WHERE id=? AND accountant_id IS NULL', (SHTYREV, cid))

for cid in andrianova_ids:
    conn.execute('UPDATE companies SET accountant_id=? WHERE id=? AND accountant_id IS NULL', (ANDRIANOVA, cid))

conn.commit()

print('=== Итог accountant_id ===')
for r in conn.execute('''SELECT a.name, count(*) FROM companies c
    LEFT JOIN accountants a ON c.accountant_id=a.id
    WHERE c.is_active=1 GROUP BY c.accountant_id ORDER BY count(*) DESC'''):
    print(f'  {r[1]:3d}  {r[0] or "NULL — без бухгалтера"}')

conn.close()
