"""
Импорт бухгалтеров и компаний из JSON-файлов в БД.
"""
import json, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

import database as db
db.init_db()

conn = sqlite3.connect('data_storage/buh_bot.db')
conn.row_factory = sqlite3.Row

# ─── 1. Загружаем бухгалтеров ─────────────────────────────────────────────────
with open('accountants_data.json', encoding='utf-8') as f:
    accountants_raw = json.load(f)

acc_name_to_id = {}
inserted_accs = 0
for a in accountants_raw:
    existing = conn.execute(
        "SELECT id FROM accountants WHERE name = ?", (a['name'],)
    ).fetchone()
    if existing:
        acc_name_to_id[a['name']] = existing['id']
        print(f"  [уже есть] {a['name']}")
    else:
        cur = conn.execute(
            "INSERT INTO accountants (name, max_user_id) VALUES (?, NULL)",
            (a['name'],)
        )
        acc_name_to_id[a['name']] = cur.lastrowid
        inserted_accs += 1
        print(f"  [добавлен] {a['name']}")

conn.commit()
print(f"\nБухгалтеров добавлено: {inserted_accs}\n")

# ─── 2. Строим сокращённый маппинг имён ───────────────────────────────────────
# В import_data.json имена сокращены: "Барышева Я." → "Барышева Яна"
def find_acc_id(short_name):
    if not short_name:
        return None
    # Точное совпадение
    if short_name in acc_name_to_id:
        return acc_name_to_id[short_name]
    # Частичное: "Барышева Я." → ищем начало фамилии + первую букву имени
    parts = short_name.strip().rstrip('.').split()
    for full_name, aid in acc_name_to_id.items():
        full_parts = full_name.split()
        if len(parts) >= 1 and len(full_parts) >= 1:
            if full_parts[0] == parts[0]:  # фамилия совпадает
                if len(parts) == 1:
                    return aid
                if len(parts) >= 2 and len(full_parts) >= 2:
                    if full_parts[1].startswith(parts[1].rstrip('.')):
                        return aid
    # Только по фамилии
    for full_name, aid in acc_name_to_id.items():
        if full_name.split()[0] == parts[0]:
            return aid
    return None

# ─── 3. Загружаем компании ────────────────────────────────────────────────────
with open('import_data.json', encoding='utf-8') as f:
    companies_raw = json.load(f)

# Формат: [name, org_type, tax_system, accountant_short_name, has_employees]
inserted_cos = 0
skipped_cos = 0
unmapped_accs = set()

# Маппинг УСН → УСН 6% (уточнить позже через /edit_company)
TAX_MAP = {'УСН': 'УСН 6%'}

for row in companies_raw:
    name, org_type, tax_system, acc_short, has_employees = row

    # Маппинг системы налогообложения
    tax_system = TAX_MAP.get(tax_system, tax_system)

    # Найти бухгалтера
    acc_id = find_acc_id(acc_short)
    if acc_short and acc_id is None:
        unmapped_accs.add(acc_short)

    existing = conn.execute(
        "SELECT id FROM companies WHERE name = ?", (name,)
    ).fetchone()
    if existing:
        skipped_cos += 1
        print(f"  [уже есть] {name}")
        continue

    conn.execute(
        """INSERT INTO companies
           (name, inn, tax_system, org_type, has_employees, has_military,
            has_stats_reporting, max_group_id, accountant_id, work_standard,
            notes, description, is_active)
           VALUES (?, NULL, ?, ?, ?, 0, 0, NULL, ?, NULL, NULL, NULL, 1)""",
        (name, tax_system, org_type, int(has_employees), acc_id)
    )
    acc_label = acc_short or '— нет'
    print(f"  [добавлена] {name} | {tax_system} | {org_type} | {acc_label}")
    inserted_cos += 1

conn.commit()
conn.close()

print(f"\n{'='*50}")
print(f"Бухгалтеров добавлено:  {inserted_accs}")
print(f"Компаний добавлено:     {inserted_cos}")
print(f"Компаний пропущено:     {skipped_cos}")
if unmapped_accs:
    print(f"\nНе найдены бухгалтеры (сокращения): {unmapped_accs}")
print("="*50)
print("Готово!")
