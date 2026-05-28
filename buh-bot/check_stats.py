import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
print('Компаний:', conn.execute('SELECT count(*) FROM companies WHERE is_active=1').fetchone()[0])
print('Бухгалтеров:', conn.execute('SELECT count(*) FROM accountants').fetchone()[0])
print('Дедлайнов:', conn.execute('SELECT count(*) FROM report_deadlines').fetchone()[0])
print('Задач:', conn.execute('SELECT count(*) FROM tasks').fetchone()[0])
print('Доп.работ:', conn.execute('SELECT count(*) FROM additional_works').fetchone()[0])
print('С описанием:', conn.execute("SELECT count(*) FROM companies WHERE description IS NOT NULL AND description != ''").fetchone()[0])
print('Ошибок (errors):', conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='errors'").fetchone()[0])
# Список всех таблиц
print('\nТаблицы в БД:')
for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cnt = conn.execute(f'SELECT count(*) FROM "{r[0]}"').fetchone()[0]
    print(f'  {r[0]}: {cnt} строк')
conn.close()
