"""
Восстанавливает привязки компаний к бухгалтерам из import_data.json.
Обновляет только компании с accountant_id IS NULL.
"""
import json, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data_storage/buh_bot.db')

# Маппинг коротких имён из JSON → id в БД
accountants = {row[0]: row[1] for row in conn.execute('SELECT name, id FROM accountants')}

NAME_MAP = {
    'Барышева Я.':      next((v for k,v in accountants.items() if k.startswith('Барышева')), None),
    'Штырева А.':       next((v for k,v in accountants.items() if k.startswith('Штырева')), None),
    'Харзеева С.':      next((v for k,v in accountants.items() if k.startswith('Харзеева')), None),
    'Сибилева Ю.Н.':   next((v for k,v in accountants.items() if k.startswith('Сибилева')), None),
    'Строкачева О.':   next((v for k,v in accountants.items() if k.startswith('Строкачева')), None),
    'Андрианова Е.':   next((v for k,v in accountants.items() if k.startswith('Андрианова')), None),
    'Аверичева М.':    next((v for k,v in accountants.items() if k.startswith('Аверичева')), None),
}

print('Маппинг бухгалтеров:')
for k, v in NAME_MAP.items():
    print(f'  {k} → id={v}')

# Загружаем import_data.json
with open('import_data.json', encoding='utf-8') as f:
    data = json.load(f)

# Компании с NULL accountant_id
null_ids = {row[0]: row[1] for row in conn.execute(
    'SELECT id, name FROM companies WHERE accountant_id IS NULL AND is_active=1'
)}

print(f'\nКомпаний без бухгалтера: {len(null_ids)}')

updated = 0
skipped = 0
for row in data:
    company_name, org_type, tax, acc_short, *_ = row
    if acc_short is None:
        continue  # изначально без бухгалтера

    acc_id = NAME_MAP.get(acc_short)
    if acc_id is None:
        continue

    # Ищем компанию в null_ids по имени (нечёткое совпадение по первому слову)
    matched = None
    for cid, cname in null_ids.items():
        if cname.upper() == company_name.upper() or cname.split()[0].upper() == company_name.split()[0].upper():
            # Дополнительная проверка — совпадение хотя бы 2 из 3 первых слов
            cn_words = set(cname.upper().split())
            jn_words = set(company_name.upper().split())
            if len(cn_words & jn_words) >= min(2, len(jn_words)):
                matched = cid
                break

    if matched:
        conn.execute('UPDATE companies SET accountant_id=? WHERE id=?', (acc_id, matched))
        print(f'  [{matched}] {null_ids[matched]} → {acc_short} (id={acc_id})')
        del null_ids[matched]
        updated += 1
    else:
        skipped += 1

conn.commit()
print(f'\nВосстановлено: {updated}')
if null_ids:
    print(f'Осталось без бухгалтера ({len(null_ids)}):')
    for cid, cname in null_ids.items():
        print(f'  [{cid}] {cname}')
conn.close()
