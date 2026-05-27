"""
Inline-клавиатуры для бота.
"""
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import CallbackButton, LinkButton
from calendar_data import TAX_SYSTEMS, ORG_TYPES, WORK_TYPES, NO_ACCOUNTANT_LABEL


def yn_keyboard(yes_payload: str, no_payload: str):
    b = InlineKeyboardBuilder()
    b.row(
        CallbackButton(text='✅ Да', payload=yes_payload),
        CallbackButton(text='❌ Нет', payload=no_payload),
    )
    return b.as_markup()


def tax_system_keyboard():
    b = InlineKeyboardBuilder()
    b.row(*[CallbackButton(text=ts, payload=f'tax:{ts}') for ts in TAX_SYSTEMS])
    return b.as_markup()


def org_type_keyboard():
    b = InlineKeyboardBuilder()
    b.row(*[CallbackButton(text=ot, payload=f'org:{ot}') for ot in ORG_TYPES])
    return b.as_markup()


def accountants_keyboard(accountants: list, prefix: str = 'acc'):
    b = InlineKeyboardBuilder()
    for a in accountants:
        b.row(CallbackButton(text=a['name'], payload=f'{prefix}:{a["id"]}'))
    b.row(CallbackButton(text=f'🚫 {NO_ACCOUNTANT_LABEL}', payload=f'{prefix}:0'))
    return b.as_markup()


def companies_keyboard(companies: list, prefix: str = 'co'):
    b = InlineKeyboardBuilder()
    for c in companies:
        b.row(CallbackButton(text=c['name'], payload=f'{prefix}:{c["id"]}'))
    return b.as_markup()


def work_types_keyboard():
    b = InlineKeyboardBuilder()
    for wt in WORK_TYPES:
        b.row(CallbackButton(text=wt, payload=f'wtype:{wt[:30]}'))
    return b.as_markup()


def priority_keyboard():
    b = InlineKeyboardBuilder()
    b.row(
        CallbackButton(text='🔽 Низкий',  payload='prio:low'),
        CallbackButton(text='➡️ Обычный', payload='prio:normal'),
        CallbackButton(text='🔺 Высокий', payload='prio:high'),
    )
    return b.as_markup()


def deadlines_keyboard(deadlines: list, prefix: str = 'done_dl'):
    b = InlineKeyboardBuilder()
    for dl in deadlines[:10]:
        label = f"✅ {dl['report_name'][:30]}"
        b.row(CallbackButton(text=label, payload=f'{prefix}:{dl["id"]}'))
    return b.as_markup()


def tasks_keyboard(tasks: list, prefix: str = 'done_task'):
    b = InlineKeyboardBuilder()
    for t in tasks[:10]:
        label = f"✅ #{t['id']} {t['title'][:25]}"
        b.row(CallbackButton(text=label, payload=f'{prefix}:{t["id"]}'))
    return b.as_markup()


def confirm_keyboard(yes_payload: str, cancel_payload: str = 'cancel'):
    b = InlineKeyboardBuilder()
    b.row(
        CallbackButton(text='✅ Подтвердить', payload=yes_payload),
        CallbackButton(text='❌ Отмена', payload=cancel_payload),
    )
    return b.as_markup()


def skip_keyboard(payload: str = 'skip'):
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text='⏩ Пропустить', payload=payload))
    return b.as_markup()


def skip_or_default_keyboard(skip_payload: str, default_payload: str):
    """Пропустить или использовать типовой стандарт."""
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text='📋 Типовой стандарт', payload=default_payload))
    b.row(CallbackButton(text='⏩ Пропустить', payload=skip_payload))
    return b.as_markup()


def cancel_keyboard():
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text='❌ Отмена', payload='cancel'))
    return b.as_markup()


def gen_deadlines_keyboard(company_id: int):
    b = InlineKeyboardBuilder()
    b.row(
        CallbackButton(text='📅 Да, создать календарь', payload=f'gen_dl:{company_id}'),
        CallbackButton(text='Позже', payload='cancel'),
    )
    return b.as_markup()


def edit_company_fields_keyboard(company_id: int):
    b = InlineKeyboardBuilder()
    fields = [
        ('Название', 'name'),
        ('ИНН', 'inn'),
        ('Описание бизнеса', 'description'),
        ('Система налогообложения', 'tax_system'),
        ('Тип организации', 'org_type'),
        ('Сотрудники', 'has_employees'),
        ('Воинский учёт', 'has_military'),
        ('Статотчётность', 'has_stats_reporting'),
        ('ID группы Max', 'max_group_id'),
        ('Бухгалтер', 'accountant_id'),
        ('Стандарт работы', 'work_standard'),
        ('Примечания', 'notes'),
    ]
    for label, field in fields:
        b.row(CallbackButton(text=label, payload=f'edit_field:{company_id}:{field}'))
    b.row(CallbackButton(text='🗑 Деактивировать компанию', payload=f'deactivate:{company_id}'))
    b.row(CallbackButton(text='❌ Отмена', payload='cancel'))
    return b.as_markup()


def report_type_keyboard():
    types = ['НДС', 'УСН', 'ЕСХН', 'Прибыль', '6-НДФЛ', 'РСВ', 'ЕФС-1',
             'БО', 'Воинский учёт', 'Статотчётность', 'Платёж НДС',
             'Платёж УСН', 'Платёж СВ', 'Платёж НДФЛ', 'Иное']
    b = InlineKeyboardBuilder()
    for t in types:
        b.row(CallbackButton(text=t, payload=f'dl_type:{t}'))
    return b.as_markup()


def admin_main_menu_v2():
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text='🏢 Компании', payload='menu:companies'))
    b.row(CallbackButton(text='👤 Бухгалтеры', payload='menu:accountants'))
    b.row(CallbackButton(text='📅 Ближайшие дедлайны (30 дн.)', payload='menu:upcoming'))
    b.row(CallbackButton(text='⚡ Срочно — 7 дней', payload='menu:week'))
    b.row(CallbackButton(text='🔴 Просроченные', payload='menu:overdue'))
    b.row(CallbackButton(text='📊 Отчёт за месяц (текст)', payload='menu:report'))
    b.row(CallbackButton(text='📥 Отчёт за месяц (Excel)', payload='menu:report_excel'))
    b.row(CallbackButton(text='📈 KPI сотрудников', payload='menu:kpi'))
    b.row(CallbackButton(text='⚠️ Журнал ошибок', payload='menu:errors'))
    b.row(CallbackButton(text='📊 Аналитика', payload='menu:analytics'))
    return b.as_markup()


def accountant_main_menu():
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text='📋 Мои задачи', payload='acc_menu:tasks'))
    b.row(CallbackButton(text='📅 Мои дедлайны', payload='acc_menu:deadlines'))
    b.row(CallbackButton(text='✅ Отметить выполненным', payload='acc_menu:mark_done'))
    b.row(CallbackButton(text='➕ Доп. работа', payload='acc_menu:add_work'))
    return b.as_markup()


def admin_main_menu():
    return admin_main_menu_v2()
