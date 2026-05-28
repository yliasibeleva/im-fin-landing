import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')

# Проверяем Антонов (id=9)
r = conn.execute('''
    SELECT c.id, c.name, c.accountant_id, a.name as acc_name,
           c.operator_id, c.payroll_accountant_id, c.hr_accountant_id
    FROM companies c
    LEFT JOIN accountants a ON c.accountant_id = a.id
    WHERE c.id = 9
''').fetchone()
print(f'Антонов id=9: accountant_id={r[2]} ({r[3]}), operator={r[4]}, payroll={r[5]}, hr={r[6]}')

# Проверяем что hr_accountant_id вообще существует как колонка
cols = [row[1] for row in conn.execute('PRAGMA table_info(companies)')]
print(f'\nКолонки companies: {cols}')
print(f'hr_accountant_id есть: {"hr_accountant_id" in cols}')
conn.close()
