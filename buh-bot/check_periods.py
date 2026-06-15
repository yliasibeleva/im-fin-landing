import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
rows = conn.execute("""
    SELECT report_type, period, due_date, report_name
    FROM report_deadlines
    WHERE due_date >= '2026-04-01' AND due_date <= '2026-12-31'
    GROUP BY report_type, period
    ORDER BY due_date
    LIMIT 40
""").fetchall()
for r in rows:
    print(f"{r[2]}  {r[1]:<20}  {r[0]:<18}  {r[3][:50]}")
conn.close()
