import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data_storage/buh_bot.db')

cur = conn.execute(
    "SELECT COUNT(*) FROM report_deadlines WHERE due_date <= '2026-06-15' AND status != 'done'"
)
count = cur.fetchone()[0]
print(f'Записей для обновления: {count}')

conn.execute(
    "UPDATE report_deadlines SET status='done', completed_at=datetime('now') WHERE due_date <= '2026-06-15' AND status != 'done'"
)
conn.commit()

cur2 = conn.execute("SELECT COUNT(*) FROM report_deadlines WHERE status = 'done'")
print(f'Итого сданных: {cur2.fetchone()[0]}')

conn.close()
print('Готово!')
