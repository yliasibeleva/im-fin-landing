"""
Назначает accountant_id для компаний с NULL из import_data.json.
Также назначает operator_id из create_table.py данных.
"""
import json, sqlite3, sys, re
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data_storage/buh_bot.db')

# Маппинг коротких имён → id бухгалтеров
accountants = {row[0]: row[1] for row in conn.execute('SELECT name, id FROM accountants')}

def find_id(short):
    if not short:
        return None
    for name, aid in accountants.items():
        first = short.split('.')[0].strip()  # "Штырева А" → "Штырева А"
        if name.startswith(first.split()[0]) and (len(first.split()) < 2 or first.split()[1][0].upper() == name.split()[1][0].upper() if len(name.split()) > 1 else True):
            return aid
    return None

# ── Фикс accountant_id из import_data.json ──────────────────────────────────
with open('import_data.json', encoding='utf-8') as f:
    data = json.load(f)

companies_db = {row[0]: row[1] for row in conn.execute(
    'SELECT name, id FROM companies WHERE is_active=1'
)}

NAME_MAP = {
    'Барышева Я.':    next((v for k,v in accountants.items() if k.startswith('Барышева')), None),
    'Штырева А.':     next((v for k,v in accountants.items() if k.startswith('Штырева')), None),
    'Харзеева С.':    next((v for k,v in accountants.items() if k.startswith('Харзеева')), None),
    'Сибилева Ю.Н.':  next((v for k,v in accountants.items() if k.startswith('Сибилева')), None),
    'Строкачева О.':  next((v for k,v in accountants.items() if k.startswith('Строкачева')), None),
    'Андрианова Е.':  next((v for k,v in accountants.items() if k.startswith('Андрианова')), None),
    'Аверичева М.':   next((v for k,v in accountants.items() if k.startswith('Аверичева')), None),
}

upd_acc = 0
for row in data:
    company_name, _, _, acc_short, *_ = row
    if not acc_short:
        continue
    acc_id = NAME_MAP.get(acc_short)
    if not acc_id:
        continue
    # Ищем компанию по имени
    for db_name, db_id in companies_db.items():
        if db_name.upper() == company_name.upper() or \
           db_name.split()[0].upper() == company_name.split()[0].upper():
            cur = conn.execute(
                'UPDATE companies SET accountant_id=? WHERE id=? AND accountant_id IS NULL',
                (acc_id, db_id)
            )
            if cur.rowcount:
                upd_acc += 1
            break

conn.commit()
print(f'accountant_id обновлено: {upd_acc} компаний')

# ── Фикс operator_id из create_table.py данных ────────────────────────────────
# Маппинг операционистов (из create_table.py) → id в БД
OP_MAP = {
    'Шалимова Л':        next((v for k,v in accountants.items() if 'Шалимов' in k), None),
    'Багрянцева Е':      next((v for k,v in accountants.items() if 'Багрянц' in k), None),
    'Мозолева А':        next((v for k,v in accountants.items() if 'Мозол' in k), None),
    'Селихова И.П.':     next((v for k,v in accountants.items() if 'Селих' in k), None),
    'Сел. И и Багр. Е': None,  # совместно — пропустим
}

raw_table = [
    ("АВТОПИЛОТ 57",             "Мозолева А"),
    ("АГРО-СЭТ",                 ""),
    ("АГРОПИЛОТ",                "Шалимова Л"),
    ("Adadurova E",              ""),
    ("Акишина НА",               ""),
    ("АЛЬТАИР",                  "Шалимова Л"),
    ("Антонов",                  ""),
    ("АПОЛЛОНИЯ",                "Шалимова Л"),
    ("АРКАДА",                   "Мозолева А"),
    ("АРКАДА старая",            ""),
    ("Астахова",                 ""),
    ("Березко АА",               "Багрянцева Е"),
    ("Березко АИ",               "Багрянцева Е"),
    ("БОТАНИКА",                 ""),
    ("Бунаков",                  "Мозолева А"),
    ("БЮРО СТРОИТЕЛЬНЫХ УСЛУГ",  ""),
    ("Верижникова Л",            "Шалимова Л"),
    ("Виолетта",                 ""),
    ("Востриков",                "Багрянцева Е"),
    ("ВУДПРЕСС-ОСП",             "Мозолева А"),
    ("ГЕФЕСТ",                   "Мозолева А"),
    ("ГК КОМПЛЕКТСЕРВИС",        "Мозолева А"),
    ("Глянцев Г",                "Шалимова Л"),
    ("ГОЛД СЕТ",                 "Мозолева А"),
    ("Горбунов АВ",              "Багрянцева Е"),
    ("Гринев СВ",                ""),
    ("Далинский",                ""),
    ("ДВА СЛОВА",                ""),
    ("ДЖЕММАРКА",                ""),
    ("ДОГГ",                     ""),
    ("ДОРОГИ ВОЙНЫ",             "Мозолева А"),
    ("Ермилов",                  "Шалимова Л"),
    ("Застрялин",                "Мозолева А"),
    ("Злобин Ю",                 "Шалимова Л"),
    ("Зорин АВ",                 ""),
    ("ИМПЕРИЯ ФИНАНС",           "Мозолева А"),
    ("ИНВЕСТ-ПРОЕКТ",            ""),
    ("Индарбиева",               "Шалимова Л"),
    ("Кирюхин С",                "Мозолева А"),
    ("КЛИМАТ ПРОФИ",             ""),
    ("Лавренин БВ",              "Шалимова Л"),
    ("Лупунчук",                 ""),
    ("Малинкина",                "Мозолева А"),
    ("Манчевская ЛЮ",            "Мозолева А"),
    ("МАСТЕР",                   "Шалимова Л"),
    ("Матвеев СЮ",               ""),
    ("Мкртумян Гарик",           "Багрянцева Е"),
    ("МОНБЛАН",                  ""),
    ("Музалевский",              ""),
    ("НАДЕЖНЫЕ ЛЮДИ",            "Шалимова Л"),
    ("НПО ВОДОЛЕЙ",              ""),
    ("Оздамиров И",              "Багрянцева Е"),
    ("Пацев С",                  "Шалимова Л"),
    ("Пашин",                    "Багрянцева Е"),
    ("ПРОФИ",                    "Мозолева А"),
    ("Пугачева Е",               ""),
    ("Райссингер В",             ""),
    ("Раннева О",                ""),
    ("Репинская",                ""),
    ("С-3 ТРАСТОВОЕ АГЕНСТВО",   ""),
    ("Савин ММ",                 "Мозолева А"),
    ("Савочкин Б",               "Мозолева А"),
    ("САКУРА",                   ""),
    ("Сальникова КП",            ""),
    ("Серпилин АА",              "Багрянцева Е"),
    ("СИБВЭЙ",                   "Мозолева А"),
    ("Сибилев",                  "Багрянцева Е"),
    ("СК 3",                     ""),
    ("СНТ НАУКА",                "Шалимова Л"),
    ("Соболев",                  "Мозолева А"),
    ("Сорокина ГС",              ""),
    ("Стариков АН",              "Шалимова Л"),
    ("СТРОЙКОМПЛЕКТ",            "Мозолева А"),
    ("Супьянов",                 ""),
    ("Тарасевич",                ""),
    ("Терехов Альберт",          "Багрянцева Е"),
    ("ТРАНСДОМТОРГ",             "Мозолева А"),
    ("ТРАСТ",                    ""),
    ("ТСЛ-КАРГО",                ""),
    ("УРАРТУ",                   "Багрянцева Е"),
    ("Фролов",                   "Шалимова Л"),
    ("ФРУТЕС",                   ""),
    ("Чижикова ИН",              ""),
    ("Шадская ОЕ",               ""),
    ("Шитова",                   ""),
    ("ЩИТ",                      ""),
    ("ЭКОМТЕХ",                  "Шалимова Л"),
    ("ЭКОСИТИ",                  ""),
    ("ЭКСПЕРТ СВ+",              "Мозолева А"),
    ("ЭМП 381",                  "Шалимова Л"),
    ("ЭМП 381 филиал",           "Шалимова Л"),
    ("ЮМАН",                     ""),
    ("ЮМАН НПЦ",                 ""),
    ("Юхненко АА",               ""),
    ("Якушева Е",                ""),
]

upd_op = 0
for company_name, op_short in raw_table:
    if not op_short:
        continue
    op_id = OP_MAP.get(op_short)
    if not op_id:
        continue
    for db_name, db_id in companies_db.items():
        if db_name.upper() == company_name.upper() or \
           db_name.split()[0].upper() == company_name.split()[0].upper():
            cur = conn.execute(
                'UPDATE companies SET operator_id=? WHERE id=?',
                (op_id, db_id)
            )
            if cur.rowcount:
                upd_op += 1
            break

conn.commit()

# Итог
print(f'operator_id обновлено:  {upd_op} компаний')
print('\n=== Итоговое распределение accountant_id ===')
for r in conn.execute('''SELECT a.name, count(*) FROM companies c
    LEFT JOIN accountants a ON c.accountant_id=a.id
    WHERE c.is_active=1 GROUP BY c.accountant_id ORDER BY count(*) DESC'''):
    print(f'  {r[1]:3d}  {r[0] or "NULL"}')

print('\n=== Итоговое распределение operator_id ===')
for r in conn.execute('''SELECT a.name, count(*) FROM companies c
    LEFT JOIN accountants a ON c.operator_id=a.id
    WHERE c.is_active=1 GROUP BY c.operator_id ORDER BY count(*) DESC'''):
    print(f'  {r[1]:3d}  {r[0] or "NULL"}')

conn.close()
