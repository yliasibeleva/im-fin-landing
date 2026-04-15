# CLAUDE.md — Инструкции для Claude Code

## О проекте

Max-бот для управления бухгалтерским аутсорсингом. Python, maxapi, SQLite, APScheduler, openpyxl.  
Все пользовательские тексты — на русском языке.

## Структура файлов

| Файл | Назначение |
|---|---|
| `main.py` | Точка входа |
| `config.py` | Настройки (читает .env) |
| `database.py` | Единый файл БД + все CRUD. **Не дробить на модули.** |
| `calendar_data.py` | Генератор дедлайнов, справочники TAX_SYSTEMS, WORK_TYPES |
| `handlers.py` | Все хендлеры dp. Декораторы `@dp.message_created`, `@dp.message_callback` |
| `keyboards.py` | Inline-клавиатуры. Все функции возвращают `b.as_markup()` |
| `states.py` | Константы состояний + класс `StateStorage` (singleton `storage`) |
| `reminders.py` | `start_scheduler(bot)` — возвращает scheduler |
| `excel_report.py` | `generate_monthly_report(year, month)` — возвращает путь к файлу |

## Правила кода

### База данных
- Используется **синхронный `sqlite3`**, вызовы из async — через `asyncio.to_thread(func, *args)`
- Все функции БД — в `database.py`, не создавать отдельные модули
- Новые таблицы добавлять в `init_db()` через `CREATE TABLE IF NOT EXISTS`
- Новые колонки к существующим таблицам — через `_migrate()` с `try/except`
- `get_db()` — контекстный менеджер, автоматический commit/rollback

### Bot API (maxapi)
- Polling режим: `await dp.start_polling(bot)`
- Команды: `@dp.message_created(Command('name'))`
- Текстовые сообщения: `@dp.message_created(F.message.body.text)`
- Callbacks: `@dp.message_callback()` или `@dp.message_callback(F.payload.startswith('prefix:'))`
- Отправка: `await event.message.answer(text, parse_mode='html', attachments=[keyboard])`
- Клавиатуры: `InlineKeyboardBuilder` + `CallbackButton(text='...', payload='...')`
- ID пользователя: `event.from_user.user_id` (int, преобразовывать в str для сравнений)
- ID чата: `event.chat.chat_id`

### Состояния диалогов
- Все константы состояний в `states.py`
- Singleton: `st.storage` — экземпляр `StateStorage`
- `st.storage.set(user_id, STATE, **data)` — устанавливает состояние с данными
- `st.storage.update(user_id, key=value)` — дописывает данные без сброса
- `st.storage.get_state(user_id)` — текущее состояние
- `st.storage.get_data(user_id)` — данные состояния
- `st.storage.clear(user_id)` — сброс

### Клавиатуры
- Все функции в `keyboards.py`, возвращают `b.as_markup()`
- Payload format: `'prefix:value'` — всегда через двоеточие
- Максимум 10 кнопок в списке (ограничение читаемости)

### Администраторы
- `ADMIN_IDS` — список строк из .env, через запятую
- Проверка: `is_admin(user_id)` — функция в `handlers.py`
- Бухгалтер определяется по `accountant_id` из таблицы accountants

## Что НЕ делать

- Не использовать webhook (только polling)
- Не дробить database.py на мелкие модули
- Не использовать async ORM (SQLAlchemy async, tortoise) — только синхронный sqlite3
- Не добавлять автоматическую интеграцию с 1С — данные вводятся вручную
- Не изменять структуру таблиц напрямую DROP/CREATE — только миграции в `_migrate()`
- Не отправлять файлы в группы клиентов — только текстовые сообщения
- Не хранить состояния в БД — только в памяти (StateStorage)

## Переменные окружения (.env)

```
BOT_TOKEN=          # токен от @MasterBot в Max
ADMIN_IDS=          # user_id через запятую
DB_PATH=            # путь к SQLite файлу
REMINDER_HOUR=9     # час отправки напоминаний (МСК)
REMINDER_DAYS=14,7,3,1  # дни до дедлайна для напоминаний
ACCOUNTANTS_GROUP_ID=   # ID общей группы бухгалтеров
MANAGERS_GROUP_ID=      # ID группы руководителей
```

## Налоговый календарь

Функция `generate_deadlines()` в `calendar_data.py` — единственный источник стандартных дедлайнов.  
При изменении налогового законодательства РФ — редактировать только её.  
Все даты пропускаются через `next_workday()` — перенос с выходных на понедельник.

## Запуск

```bash
pip install -r requirements.txt
cp .env.example .env
# заполнить .env
python main.py
```

## Типичные задачи по расширению

**Добавить новую команду:**
1. Добавить состояния в `states.py` если нужен диалог
2. Добавить клавиатуры в `keyboards.py` если нужны кнопки
3. Добавить CRUD в `database.py` если нужна БД
4. Добавить хендлер в `handlers.py`

**Добавить новый тип отчётности:**
- Редактировать `generate_deadlines()` в `calendar_data.py`

**Добавить новый тип доп. работ:**
- Добавить в список `WORK_TYPES` в `calendar_data.py`

**Добавить новое поле в компанию:**
1. Добавить колонку в `CREATE TABLE` в `init_db()`
2. Добавить в `_migrate()` через `ALTER TABLE`
3. Обновить `add_company()` и `update_company()`
4. Добавить шаг в диалог `/add_company` в `handlers.py`
