import json, sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data_storage/buh_bot.db')
with open('accountants_data.json', encoding='utf-8') as f:
    data = json.load(f)
for a in data:
    conn.execute(
        "UPDATE accountants SET position=?, phone=?, email=?, tg=?, is_remote=? WHERE name=?",
        (a.get('position'), a.get('phone'), a.get('email'), a.get('tg'), int(a.get('is_remote',0)), a['name'])
    )
    print(f"  {a['name']} | {a.get('position','—')} | {a.get('phone','—')}")
conn.commit()
conn.close()
print('готово')
