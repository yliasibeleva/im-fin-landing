"""
Все обработчики бота.

АРХИТЕКТУРНОЕ ПРАВИЛО:
  - Ровно один @dp.message_created(F.message.body.text)
  - Ровно один @dp.message_callback()
  Вся маршрутизация — внутри этих двух функций.
  Конкретные @dp.message_callback(F.payload...) не использовать —
  в maxapi catch-all блокирует специфичные, зарегистрированные после него.
"""
import asyncio
import logging
from datetime import date, datetime

from maxapi import Bot, Dispatcher
from maxapi.filters import F, Command
from maxapi.types import MessageCreated, MessageCallback

import database as db
import keyboards as kb
import states as st
import excel_report
from calendar_data import (
    generate_deadlines, TAX_SYSTEMS, ORG_TYPES, WORK_TYPES,
    STATUS_LABELS, PRIORITY_LABELS
)
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

dp = Dispatcher()


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def is_admin(user_id) -> bool:
    return str(user_id) in ADMIN_IDS


def fmt_date(iso_date: str) -> str:
    if not iso_date:
        return '—'
    try:
        return date.fromisoformat(iso_date[:10]).strftime('%d.%m.%Y')
    except ValueError:
        return iso_date


def days_left(iso_date: str) -> int:
    try:
        return (date.fromisoformat(iso_date[:10]) - date.today()).days
    except ValueError:
        return 0


def deadline_emoji(iso_date: str, status: str) -> str:
    if status == 'done':
        return '✅'
    dl = days_left(iso_date)
    if dl < 0:   return '🔴'
    if dl <= 3:  return '🟠'
    if dl <= 7:  return '🟡'
    return '🟢'


async def run_db(func, *args):
    return await asyncio.to_thread(func, *args)


# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message_created(Command('start'))
async def cmd_start(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    st.storage.clear(user_id)
    if is_admin(user_id):
        await event.message.answer(
            f"👋 Добро пожаловать, руководитель!\n\n"
            f"🤖 Бот управления бухгалтерским аутсорсингом\n"
            f"Ваш ID: <b>{user_id}</b>",
            parse_mode='html',
            attachments=[kb.admin_main_menu_v2()]
        )
    else:
        acc = await run_db(db.get_accountant_by_user_id, user_id)
        if acc:
            await event.message.answer(
                f"👋 Привет, <b>{acc['name']}</b>!\nВаш ID: <b>{user_id}</b>",
                parse_mode='html',
                attachments=[kb.accountant_main_menu()]
            )
        else:
            await event.message.answer(
                f"👋 Привет!\nВаш ID: <b>{user_id}</b>\n\n"
                f"Вы не зарегистрированы. Сообщите этот ID руководителю.",
                parse_mode='html'
            )


# ─── /myid ────────────────────────────────────────────────────────────────────

@dp.message_created(Command('myid'))
async def cmd_myid(event: MessageCreated):
    await event.message.answer(
        f"👤 user_id: <b>{event.from_user.user_id}</b>\n"
        f"💬 chat_id: <b>{event.chat.chat_id}</b>",
        parse_mode='html'
    )


# ─── /status (в группе клиента) ───────────────────────────────────────────────

@dp.message_created(Command('status'))
async def cmd_status(event: MessageCreated):
    chat_id = str(event.chat.chat_id)
    company = await run_db(db.get_company_by_group_id, chat_id)
    if not company:
        await event.message.answer(
            "⚠️ Эта группа не привязана к компании. Обратитесь к руководителю."
        )
        return
    deadlines = await run_db(db.get_deadlines_for_company, company['id'], 'pending')
    upcoming = [d for d in deadlines if days_left(d['due_date']) >= 0][:15]
    if not upcoming:
        await event.message.answer(
            f"✅ У <b>{company['name']}</b> нет ближайших дедлайнов.", parse_mode='html'
        )
        return
    lines = [f"📋 <b>Дедлайны: {company['name']}</b>\n"]
    for dl in upcoming:
        emoji = deadline_emoji(dl['due_date'], dl['status'])
        lines.append(f"{emoji} {fmt_date(dl['due_date'])} — {dl['report_name']} ({days_left(dl['due_date'])} дн.)")
    await event.message.answer('\n'.join(lines), parse_mode='html')


# ─── Команды добавления (admin) ───────────────────────────────────────────────

@dp.message_created(Command('add_company'))
async def cmd_add_company(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    st.storage.set(user_id, st.ADD_CO_NAME)
    await event.message.answer(
        "🏢 <b>Добавление компании</b>\n\nШаг 1/9. Введите <b>название</b>:",
        parse_mode='html', attachments=[kb.cancel_keyboard()]
    )


@dp.message_created(Command('add_accountant'))
async def cmd_add_accountant(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    st.storage.set(user_id, st.ADD_ACC_NAME)
    await event.message.answer(
        "👤 <b>Добавление бухгалтера</b>\n\nВведите ФИО:",
        parse_mode='html', attachments=[kb.cancel_keyboard()]
    )


@dp.message_created(Command('add_task'))
async def cmd_add_task(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    companies = await run_db(db.get_all_companies)
    if not companies:
        await event.message.answer("Сначала добавьте компании: /add_company"); return
    st.storage.set(user_id, st.ADD_TASK_COMPANY)
    await event.message.answer(
        "📋 <b>Новая задача</b>\n\nВыберите компанию:",
        parse_mode='html', attachments=[kb.companies_keyboard(companies, 'task_co')]
    )


@dp.message_created(Command('add_deadline'))
async def cmd_add_deadline(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    companies = await run_db(db.get_all_companies)
    if not companies:
        await event.message.answer("Сначала добавьте компании."); return
    st.storage.set(user_id, st.ADD_DL_COMPANY)
    await event.message.answer(
        "📅 <b>Добавление дедлайна</b>\n\nВыберите компанию:",
        parse_mode='html', attachments=[kb.companies_keyboard(companies, 'dl_co')]
    )


@dp.message_created(Command('edit_company'))
async def cmd_edit_company(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    companies = await run_db(db.get_all_companies)
    if not companies:
        await event.message.answer("Нет компаний."); return
    st.storage.set(user_id, st.EDIT_CO_SELECT)
    await event.message.answer(
        "🏢 <b>Редактирование компании</b>\n\nВыберите:",
        parse_mode='html', attachments=[kb.companies_keyboard(companies, 'editco')]
    )


@dp.message_created(Command('add_error'))
async def cmd_add_error(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    accs = await run_db(db.get_all_accountants)
    if not accs:
        await event.message.answer("Бухгалтеры не добавлены."); return
    st.storage.set(user_id, st.ADD_ERR_ACCOUNTANT)
    await event.message.answer(
        "⚠️ <b>Фиксация ошибки</b>\n\nВыберите бухгалтера:",
        parse_mode='html', attachments=[kb.accountants_keyboard(accs, 'err_acc')]
    )


@dp.message_created(Command('company_info'))
async def cmd_company_info(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    companies = await run_db(db.get_all_companies)
    if not companies:
        await event.message.answer("Нет компаний."); return
    await event.message.answer(
        "Выберите компанию:", attachments=[kb.companies_keyboard(companies, 'info_co')]
    )


@dp.message_created(Command('add_work'))
async def cmd_add_work(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    acc = await run_db(db.get_accountant_by_user_id, user_id)
    if not acc and not is_admin(user_id):
        await event.message.answer("Вы не зарегистрированы."); return
    companies = (
        await run_db(db.get_companies_by_accountant, acc['id'])
        if acc else await run_db(db.get_all_companies)
    )
    if not companies:
        await event.message.answer("Нет активных компаний."); return
    st.storage.set(user_id, st.ADD_WORK_COMPANY,
                   accountant_id=acc['id'] if acc else None)
    await event.message.answer(
        "➕ <b>Доп. работа</b>\n\nВыберите компанию:",
        parse_mode='html', attachments=[kb.companies_keyboard(companies, 'work_co')]
    )


@dp.message_created(Command('mytasks'))
async def cmd_mytasks(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    acc = await run_db(db.get_accountant_by_user_id, user_id)
    if not acc:
        await event.message.answer("Вы не зарегистрированы."); return
    tasks = await run_db(db.get_tasks_for_accountant, acc['id'], 'pending')
    if not tasks:
        await event.message.answer("✅ Нет активных задач!"); return
    lines = ["📋 <b>Ваши задачи:</b>\n"]
    for t in tasks:
        due = fmt_date(t['due_date']) if t['due_date'] else '—'
        prio = PRIORITY_LABELS.get(t['priority'], t['priority'])
        lines.append(f"#{t['id']} | {prio}\n  {t['title']}\n  🏢 {t['company_name'] or '—'} | 📅 {due}")
    await event.message.answer(
        '\n'.join(lines), parse_mode='html', attachments=[kb.tasks_keyboard(tasks)]
    )


@dp.message_created(Command('mydeadlines'))
async def cmd_mydeadlines(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    acc = await run_db(db.get_accountant_by_user_id, user_id)
    if not acc:
        await event.message.answer("Вы не зарегистрированы."); return
    await _send_accountant_deadlines(event, acc)


@dp.message_created(Command('upcoming'))
async def cmd_upcoming(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    if not is_admin(user_id): return
    deadlines = await run_db(db.get_upcoming_deadlines, 30)
    if not deadlines:
        await event.message.answer("✅ На 30 дней дедлайнов нет."); return
    lines = ["📅 <b>Дедлайны на 30 дней:</b>\n"]
    for dl in deadlines[:40]:
        emoji = deadline_emoji(dl['due_date'], dl['status'])
        acc = dl['accountant_name'] or '—'
        lines.append(
            f"{emoji} {fmt_date(dl['due_date'])} | {dl['company_name']}\n"
            f"    {dl['report_name']} | {acc} | {days_left(dl['due_date'])} дн."
        )
    await event.message.answer('\n'.join(lines), parse_mode='html')


# ─── Единый обработчик текста ─────────────────────────────────────────────────
# ВАЖНО: ровно один @dp.message_created(F.message.body.text) на весь файл.

@dp.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    user_id = str(event.from_user.user_id)
    text = event.message.body.text.strip()
    state = st.storage.get_state(user_id)

    if not state:
        return

    if text.lower() in ('/cancel', 'отмена', '/отмена'):
        st.storage.clear(user_id)
        await event.message.answer("❌ Отменено.")
        return

    # ══ ДОБАВЛЕНИЕ КОМПАНИИ ════════════════════════════════════════════════════

    if state == st.ADD_CO_NAME:
        st.storage.update(user_id, name=text)
        st.storage.set(user_id, st.ADD_CO_INN, **st.storage.get_data(user_id))
        await event.message.answer(
            f"Название: <b>{text}</b>\n\nШаг 2/9. Введите <b>ИНН</b> (или «Пропустить»):",
            parse_mode='html', attachments=[kb.skip_keyboard('skip_inn')]
        )

    elif state == st.ADD_CO_INN:
        st.storage.update(user_id, inn=text)
        st.storage.set(user_id, st.ADD_CO_TAX, **st.storage.get_data(user_id))
        await event.message.answer(
            "Шаг 3/9. Выберите <b>систему налогообложения</b>:",
            parse_mode='html', attachments=[kb.tax_system_keyboard()]
        )

    elif state == st.ADD_CO_GROUP:
        st.storage.update(user_id, max_group_id=text)
        st.storage.set(user_id, st.ADD_CO_ACCOUNTANT, **st.storage.get_data(user_id))
        await _ask_accountant(event, user_id)

    elif state == st.ADD_CO_STANDARD:
        st.storage.update(user_id, work_standard=text)
        await _save_company(event, user_id)

    # ══ ДОБАВЛЕНИЕ БУХГАЛТЕРА ══════════════════════════════════════════════════

    elif state == st.ADD_ACC_NAME:
        st.storage.update(user_id, acc_name=text)
        st.storage.set(user_id, st.ADD_ACC_MAX_ID, **st.storage.get_data(user_id))
        await event.message.answer(
            f"ФИО: <b>{text}</b>\n\nВведите <b>Max user_id</b> бухгалтера\n"
            f"(бухгалтер пишет /myid боту)\nИли «Пропустить»:",
            parse_mode='html', attachments=[kb.skip_keyboard('skip_acc_id')]
        )

    elif state == st.ADD_ACC_MAX_ID:
        data = st.storage.get_data(user_id)
        acc_id = await run_db(db.add_accountant, data['acc_name'], text)
        st.storage.clear(user_id)
        await event.message.answer(
            f"✅ Бухгалтер <b>{data['acc_name']}</b> добавлен (#{acc_id}).",
            parse_mode='html'
        )

    # ══ ДОП. РАБОТА ════════════════════════════════════════════════════════════

    elif state == st.ADD_WORK_DESC:
        st.storage.update(user_id, description=text)
        st.storage.set(user_id, st.ADD_WORK_HOURS, **st.storage.get_data(user_id))
        await event.message.answer(
            "Сколько <b>часов</b>? (например 2.5, или 0):", parse_mode='html'
        )

    elif state == st.ADD_WORK_HOURS:
        try:
            hours = float(text.replace(',', '.'))
        except ValueError:
            await event.message.answer("Введите число, например: 1.5"); return
        st.storage.update(user_id, hours=hours)
        st.storage.set(user_id, st.ADD_WORK_AMOUNT, **st.storage.get_data(user_id))
        await event.message.answer(
            "Стоимость в <b>рублях</b> (или 0):", parse_mode='html'
        )

    elif state == st.ADD_WORK_AMOUNT:
        try:
            amount = float(text.replace(',', '.').replace(' ', ''))
        except ValueError:
            await event.message.answer("Введите число, например: 5000"); return
        st.storage.update(user_id, amount=amount)
        st.storage.set(user_id, st.ADD_WORK_DATE, **st.storage.get_data(user_id))
        today_str = date.today().strftime('%d.%m.%Y')
        await event.message.answer(
            f"Дата (ДД.ММ.ГГГГ) или «Пропустить» для сегодня ({today_str}):",
            attachments=[kb.skip_keyboard('skip_work_date')]
        )

    elif state == st.ADD_WORK_DATE:
        try:
            work_date = datetime.strptime(text, '%d.%m.%Y').date().isoformat()
        except ValueError:
            await event.message.answer("Формат: ДД.ММ.ГГГГ"); return
        await _save_work(event, user_id, work_date)

    # ══ ЗАДАЧА ═════════════════════════════════════════════════════════════════

    elif state == st.ADD_TASK_TITLE:
        st.storage.update(user_id, title=text)
        st.storage.set(user_id, st.ADD_TASK_DESC, **st.storage.get_data(user_id))
        await event.message.answer(
            f"Задача: <b>{text}</b>\n\nОписание (или «Пропустить»):",
            parse_mode='html', attachments=[kb.skip_keyboard('skip_task_desc')]
        )

    elif state == st.ADD_TASK_DESC:
        st.storage.update(user_id, task_desc=text)
        st.storage.set(user_id, st.ADD_TASK_DUE, **st.storage.get_data(user_id))
        await event.message.answer(
            "Срок (ДД.ММ.ГГГГ) или «Пропустить»:",
            attachments=[kb.skip_keyboard('skip_task_due')]
        )

    elif state == st.ADD_TASK_DUE:
        try:
            due_date = datetime.strptime(text, '%d.%m.%Y').date().isoformat()
        except ValueError:
            await event.message.answer("Формат: ДД.ММ.ГГГГ"); return
        st.storage.update(user_id, due_date=due_date)
        st.storage.set(user_id, st.ADD_TASK_PRIORITY, **st.storage.get_data(user_id))
        await event.message.answer("Приоритет:", attachments=[kb.priority_keyboard()])

    # ══ ДЕДЛАЙН (произвольный) ═════════════════════════════════════════════════

    elif state == st.ADD_DL_NAME:
        st.storage.update(user_id, dl_name=text)
        st.storage.set(user_id, st.ADD_DL_TYPE, **st.storage.get_data(user_id))
        await event.message.answer(
            f"Название: <b>{text}</b>\n\nВыберите тип дедлайна:",
            parse_mode='html', attachments=[kb.report_type_keyboard()]
        )

    elif state == st.ADD_DL_DATE:
        try:
            dl_date = datetime.strptime(text, '%d.%m.%Y').date().isoformat()
        except ValueError:
            await event.message.answer("Формат: ДД.ММ.ГГГГ"); return
        st.storage.update(user_id, dl_date=dl_date)
        st.storage.set(user_id, st.ADD_DL_PERIOD, **st.storage.get_data(user_id))
        await event.message.answer(
            f"Дата: <b>{text}</b>\n\nПериод (например «Q1/2026») или «Пропустить»:",
            parse_mode='html', attachments=[kb.skip_keyboard('skip_dl_period')]
        )

    elif state == st.ADD_DL_PERIOD:
        await _save_deadline(event, user_id, period=text)

    # ══ РЕДАКТИРОВАНИЕ КОМПАНИИ ════════════════════════════════════════════════

    elif state == st.EDIT_CO_VALUE:
        data = st.storage.get_data(user_id)
        co_id = data.get('edit_company_id')
        field = data.get('edit_field')
        if co_id and field:
            await run_db(db.update_company, co_id, **{field: text})
            st.storage.clear(user_id)
            await event.message.answer("✅ Изменение сохранено.")

    # ══ ОШИБКА БУХГАЛТЕРА ══════════════════════════════════════════════════════

    elif state == st.ADD_ERR_DESC:
        st.storage.update(user_id, err_description=text)
        st.storage.set(user_id, st.ADD_ERR_DATE, **st.storage.get_data(user_id))
        today_str = date.today().strftime('%d.%m.%Y')
        await event.message.answer(
            f"Дата ошибки (ДД.ММ.ГГГГ) или «Пропустить» ({today_str}):",
            attachments=[kb.skip_keyboard('skip_err_date')]
        )

    elif state == st.ADD_ERR_DATE:
        try:
            err_date = datetime.strptime(text, '%d.%m.%Y').date().isoformat()
        except ValueError:
            await event.message.answer("Формат: ДД.ММ.ГГГГ"); return
        await _save_error(event, user_id, err_date)

    else:
        # Состояние ожидает нажатия кнопки — текст не обрабатывается
        await event.message.answer("Пожалуйста, используйте кнопки 👇")


# ─── Единый обработчик callbacks ─────────────────────────────────────────────
# ВАЖНО: ровно один @dp.message_callback() на весь файл.
# Специфичные @dp.message_callback(F.payload...) НЕ использовать —
# в maxapi они не вызываются если catch-all зарегистрирован раньше.

@dp.message_callback()
async def callback_handler(callback: MessageCallback):
    user_id = str(callback.from_user.user_id)
    payload = callback.payload or ''
    state = st.storage.get_state(user_id)

    # ── Отмена ────────────────────────────────────────────────────────────────
    if payload == 'cancel':
        st.storage.clear(user_id)
        await callback.message.answer("❌ Отменено.")
        return

    # ── Главное меню ──────────────────────────────────────────────────────────
    if payload.startswith('menu:'):
        if not is_admin(user_id): return
        action = payload.split(':', 1)[1]
        if action == 'companies':      await _show_companies(callback)
        elif action == 'accountants':  await _show_accountants(callback)
        elif action == 'upcoming':     await _show_upcoming(callback)
        elif action == 'overdue':      await _show_overdue(callback)
        elif action == 'report':       await _show_monthly_report(callback)
        elif action == 'report_excel': await _send_excel_report(callback)
        elif action == 'kpi':          await _show_kpi(callback)
        elif action == 'errors':       await _show_errors_log(callback)
        return

    # ── Меню бухгалтера ───────────────────────────────────────────────────────
    if payload.startswith('acc_menu:'):
        await _handle_acc_menu(callback, payload, user_id)
        return

    # ── Пропуски ──────────────────────────────────────────────────────────────
    if payload == 'skip_inn':
        st.storage.update(user_id, inn=None)
        st.storage.set(user_id, st.ADD_CO_TAX, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Шаг 3/9. Выберите <b>систему налогообложения</b>:",
            parse_mode='html', attachments=[kb.tax_system_keyboard()]
        )
        return

    if payload == 'skip_acc_id':
        data = st.storage.get_data(user_id)
        acc_id = await run_db(db.add_accountant, data['acc_name'], None)
        st.storage.clear(user_id)
        await callback.message.answer(
            f"✅ Бухгалтер <b>{data['acc_name']}</b> добавлен (#{acc_id}).",
            parse_mode='html'
        )
        return

    if payload == 'skip_work_date':
        await _save_work(callback, user_id, date.today().isoformat())
        return

    if payload == 'skip_standard':
        st.storage.update(user_id, work_standard=None)
        await _save_company(callback, user_id)
        return

    if payload == 'skip_task_desc':
        st.storage.update(user_id, task_desc=None)
        st.storage.set(user_id, st.ADD_TASK_DUE, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Срок (ДД.ММ.ГГГГ) или «Пропустить»:",
            attachments=[kb.skip_keyboard('skip_task_due')]
        )
        return

    if payload == 'skip_task_due':
        st.storage.update(user_id, due_date=None)
        st.storage.set(user_id, st.ADD_TASK_PRIORITY, **st.storage.get_data(user_id))
        await callback.message.answer("Приоритет:", attachments=[kb.priority_keyboard()])
        return

    if payload == 'skip_group':
        st.storage.update(user_id, max_group_id=None)
        st.storage.set(user_id, st.ADD_CO_ACCOUNTANT, **st.storage.get_data(user_id))
        await _ask_accountant(callback, user_id)
        return

    if payload == 'skip_dl_period':
        await _save_deadline(callback, user_id, period=None)
        return

    if payload == 'skip_err_date':
        await _save_error(callback, user_id, date.today().isoformat())
        return

    # ── Система налогообложения ───────────────────────────────────────────────
    # Обрабатываем с учётом контекста: добавление или редактирование
    if payload.startswith('tax:'):
        ts = payload.split(':', 1)[1]
        if state == st.EDIT_CO_VALUE:
            data = st.storage.get_data(user_id)
            await run_db(db.update_company, data['edit_company_id'], tax_system=ts)
            st.storage.clear(user_id)
            await callback.message.answer(f"✅ СНО обновлена: <b>{ts}</b>.", parse_mode='html')
        else:
            # Поток добавления компании
            st.storage.update(user_id, tax_system=ts)
            st.storage.set(user_id, st.ADD_CO_ORG, **st.storage.get_data(user_id))
            await callback.message.answer(
                f"СНО: <b>{ts}</b>\n\nШаг 4/9. Тип организации:",
                parse_mode='html', attachments=[kb.org_type_keyboard()]
            )
        return

    # ── Тип организации ───────────────────────────────────────────────────────
    if payload.startswith('org:'):
        org = payload.split(':', 1)[1]
        if state == st.EDIT_CO_VALUE:
            data = st.storage.get_data(user_id)
            await run_db(db.update_company, data['edit_company_id'], org_type=org)
            st.storage.clear(user_id)
            await callback.message.answer(f"✅ Тип обновлён: <b>{org}</b>.", parse_mode='html')
        else:
            st.storage.update(user_id, org_type=org)
            st.storage.set(user_id, st.ADD_CO_EMPLOYEES, **st.storage.get_data(user_id))
            await callback.message.answer(
                f"Тип: <b>{org}</b>\n\nШаг 5/9. Есть <b>сотрудники</b>?",
                parse_mode='html', attachments=[kb.yn_keyboard('emp:yes', 'emp:no')]
            )
        return

    # ── Сотрудники ────────────────────────────────────────────────────────────
    if payload in ('emp:yes', 'emp:no'):
        has_emp = payload == 'emp:yes'
        if state == st.EDIT_CO_VALUE:
            data = st.storage.get_data(user_id)
            await run_db(db.update_company, data['edit_company_id'], has_employees=int(has_emp))
            st.storage.clear(user_id)
            await callback.message.answer("✅ Обновлено.")
        else:
            st.storage.update(user_id, has_employees=has_emp)
            st.storage.set(user_id, st.ADD_CO_MILITARY, **st.storage.get_data(user_id))
            await callback.message.answer(
                f"Сотрудники: <b>{'Да' if has_emp else 'Нет'}</b>\n\nШаг 6/9. <b>Воинский учёт</b>?",
                parse_mode='html', attachments=[kb.yn_keyboard('mil:yes', 'mil:no')]
            )
        return

    # ── Воинский учёт ─────────────────────────────────────────────────────────
    if payload in ('mil:yes', 'mil:no'):
        has_mil = payload == 'mil:yes'
        if state == st.EDIT_CO_VALUE:
            data = st.storage.get_data(user_id)
            await run_db(db.update_company, data['edit_company_id'], has_military=int(has_mil))
            st.storage.clear(user_id)
            await callback.message.answer("✅ Обновлено.")
        else:
            st.storage.update(user_id, has_military=has_mil)
            st.storage.set(user_id, st.ADD_CO_GROUP, **st.storage.get_data(user_id))
            await callback.message.answer(
                f"Воинский учёт: <b>{'Да' if has_mil else 'Нет'}</b>\n\n"
                f"Шаг 7/9. Введите <b>ID группы Max</b> для уведомлений\n"
                f"(напишите /myid в нужной группе)\nИли «Пропустить»:",
                parse_mode='html', attachments=[kb.skip_keyboard('skip_group')]
            )
        return

    # ── Булевы поля при редактировании ────────────────────────────────────────
    if payload.startswith('edit_bool:'):
        _, field, val_str = payload.split(':', 2)
        data = st.storage.get_data(user_id)
        co_id = data.get('edit_company_id')
        if co_id:
            await run_db(db.update_company, co_id, **{field: int(val_str)})
            st.storage.clear(user_id)
            await callback.message.answer("✅ Изменение сохранено.")
        return

    # ── Выбор бухгалтера для компании (добавление) ────────────────────────────
    if payload.startswith('acc:'):
        acc_id_str = payload.split(':', 1)[1]
        acc_id = int(acc_id_str) if acc_id_str != '0' else None
        st.storage.update(user_id, accountant_id=acc_id)
        st.storage.set(user_id, st.ADD_CO_STANDARD, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Шаг 9/9. Опишите <b>стандарт работы</b> (что входит в базовый пакет).\n\n"
            "Пример:\n✅ Бухучёт (ОСН)\n✅ Расчёт зарплаты (3 чел.)\n"
            "✅ Кадровое делопроизводство\n✅ Квартальная отчётность\n\n"
            "Или нажмите «Пропустить»:",
            parse_mode='html', attachments=[kb.skip_keyboard('skip_standard')]
        )
        return

    # ── Генерация дедлайнов ───────────────────────────────────────────────────
    if payload.startswith('gen_dl:'):
        company_id = int(payload.split(':', 1)[1])
        company = await run_db(db.get_company, company_id)
        if not company:
            await callback.message.answer("Компания не найдена."); return
        deadlines = generate_deadlines(
            company_id=company_id,
            tax_system=company['tax_system'],
            org_type=company['org_type'] or 'ООО',
            has_employees=bool(company['has_employees']),
            has_military=bool(company['has_military']),
        )
        await run_db(db.add_deadlines_bulk, deadlines)
        await callback.message.answer(
            f"📅 Создано <b>{len(deadlines)}</b> дедлайнов для <b>{company['name']}</b>!",
            parse_mode='html'
        )
        return

    # ── Отметить дедлайн выполненным ──────────────────────────────────────────
    if payload.startswith('done_dl:'):
        dl_id = int(payload.split(':', 1)[1])
        dl = await run_db(db.get_deadline, dl_id)
        if not dl:
            await callback.message.answer("Дедлайн не найден."); return
        await run_db(db.mark_deadline_done, dl_id)
        await callback.message.answer(
            f"✅ <b>{dl['report_name']}</b> ({dl['company_name']}) — выполнено!",
            parse_mode='html'
        )
        return

    # ── Отметить задачу выполненной ───────────────────────────────────────────
    if payload.startswith('done_task:'):
        task_id = int(payload.split(':', 1)[1])
        task = await run_db(db.get_task, task_id)
        if not task:
            await callback.message.answer("Задача не найдена."); return
        await run_db(db.mark_task_done, task_id)
        await callback.message.answer(
            f"✅ Задача #{task_id} «{task['title']}» — выполнена!", parse_mode='html'
        )
        return

    # ── Выбор компании для доп. работы ────────────────────────────────────────
    if payload.startswith('work_co:'):
        co_id = int(payload.split(':', 1)[1])
        st.storage.update(user_id, company_id=co_id)
        st.storage.set(user_id, st.ADD_WORK_TYPE, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Выберите <b>тип</b> доп. работы:",
            parse_mode='html', attachments=[kb.work_types_keyboard()]
        )
        return

    # ── Тип доп. работы ───────────────────────────────────────────────────────
    if payload.startswith('wtype:'):
        wtype_short = payload.split(':', 1)[1]
        full_type = next((w for w in WORK_TYPES if w.startswith(wtype_short)), wtype_short)
        st.storage.update(user_id, work_type=full_type)
        st.storage.set(user_id, st.ADD_WORK_DESC, **st.storage.get_data(user_id))
        await callback.message.answer(
            f"Тип: <b>{full_type}</b>\n\nОпишите выполненную работу:",
            parse_mode='html'
        )
        return

    # ── Выбор компании для задачи ─────────────────────────────────────────────
    if payload.startswith('task_co:'):
        co_id = int(payload.split(':', 1)[1])
        st.storage.update(user_id, company_id=co_id)
        st.storage.set(user_id, st.ADD_TASK_ACCOUNTANT, **st.storage.get_data(user_id))
        accs = await run_db(db.get_all_accountants)
        await callback.message.answer(
            "Назначьте <b>бухгалтера</b>:",
            parse_mode='html', attachments=[kb.accountants_keyboard(accs, 'task_acc')]
        )
        return

    # ── Выбор бухгалтера для задачи ───────────────────────────────────────────
    if payload.startswith('task_acc:'):
        acc_id_str = payload.split(':', 1)[1]
        acc_id = int(acc_id_str) if acc_id_str != '0' else None
        st.storage.update(user_id, task_accountant_id=acc_id)
        st.storage.set(user_id, st.ADD_TASK_TITLE, **st.storage.get_data(user_id))
        await callback.message.answer("Введите <b>название задачи</b>:", parse_mode='html')
        return

    # ── Приоритет задачи ──────────────────────────────────────────────────────
    if payload.startswith('prio:'):
        priority = payload.split(':', 1)[1]
        data = st.storage.get_data(user_id)
        task_id = await run_db(
            db.add_task,
            data.get('title', ''),
            data.get('company_id'),
            data.get('task_accountant_id'),
            data.get('task_desc'),
            data.get('due_date'),
            priority
        )
        st.storage.clear(user_id)
        await callback.message.answer(
            f"✅ Задача #{task_id} создана!\n<b>{data.get('title')}</b>", parse_mode='html'
        )
        return

    # ── Дедлайн: выбор компании ───────────────────────────────────────────────
    if payload.startswith('dl_co:'):
        co_id = int(payload.split(':', 1)[1])
        st.storage.update(user_id, company_id=co_id)
        st.storage.set(user_id, st.ADD_DL_NAME, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Введите <b>название</b> дедлайна\n(например: «Декларация НДС»):",
            parse_mode='html'
        )
        return

    # ── Дедлайн: тип ─────────────────────────────────────────────────────────
    if payload.startswith('dl_type:'):
        dl_type = payload.split(':', 1)[1]
        st.storage.update(user_id, dl_type=dl_type)
        st.storage.set(user_id, st.ADD_DL_DATE, **st.storage.get_data(user_id))
        await callback.message.answer(
            f"Тип: <b>{dl_type}</b>\n\nВведите <b>дату</b> (ДД.ММ.ГГГГ):",
            parse_mode='html'
        )
        return

    # ── Редактирование: выбор компании ────────────────────────────────────────
    if payload.startswith('editco:'):
        co_id = int(payload.split(':', 1)[1])
        company = await run_db(db.get_company, co_id)
        if not company:
            await callback.message.answer("Компания не найдена."); return
        st.storage.set(user_id, st.EDIT_CO_FIELD, edit_company_id=co_id)
        info = (
            f"🏢 <b>{company['name']}</b>\n"
            f"ИНН: {company['inn'] or '—'} | {company['tax_system']} | {company['org_type'] or '—'}\n"
            f"Сотрудники: {'Да' if company['has_employees'] else 'Нет'} | "
            f"Воинский учёт: {'Да' if company['has_military'] else 'Нет'}\n"
            f"Бухгалтер: {company['accountant_name'] or '—'}\n"
            f"Max-группа: {company['max_group_id'] or 'не привязана'}\n\n"
            f"<b>Стандарт работы:</b>\n{company['work_standard'] or '— не заполнен —'}\n\n"
            f"Что редактируем?"
        )
        await callback.message.answer(
            info, parse_mode='html',
            attachments=[kb.edit_company_fields_keyboard(co_id)]
        )
        return

    # ── Редактирование: выбор поля ────────────────────────────────────────────
    if payload.startswith('edit_field:'):
        _, co_id_str, field = payload.split(':', 2)
        co_id = int(co_id_str)
        st.storage.set(user_id, st.EDIT_CO_VALUE, edit_company_id=co_id, edit_field=field)

        if field in ('has_employees', 'has_military'):
            label = 'сотрудники' if field == 'has_employees' else 'воинский учёт'
            await callback.message.answer(
                f"{'Есть' if field == 'has_employees' else 'Нужен'} <b>{label}</b>?",
                parse_mode='html',
                attachments=[kb.yn_keyboard(f'edit_bool:{field}:1', f'edit_bool:{field}:0')]
            )
        elif field == 'tax_system':
            await callback.message.answer(
                "Выберите систему налогообложения:",
                attachments=[kb.tax_system_keyboard()]
            )
        elif field == 'org_type':
            await callback.message.answer(
                "Выберите тип организации:", attachments=[kb.org_type_keyboard()]
            )
        elif field == 'accountant_id':
            accs = await run_db(db.get_all_accountants)
            await callback.message.answer(
                "Выберите бухгалтера:", attachments=[kb.accountants_keyboard(accs, 'edit_acc')]
            )
        elif field == 'work_standard':
            await callback.message.answer(
                "Введите <b>стандарт работы</b>:\n\n"
                "Пример:\n✅ Бухучёт (ОСН)\n✅ Расчёт зарплаты\n"
                "✅ Кадровый учёт\n✅ Квартальная отчётность",
                parse_mode='html'
            )
        else:
            field_labels = {
                'name': 'название', 'inn': 'ИНН',
                'max_group_id': 'ID группы Max', 'notes': 'примечание'
            }
            await callback.message.answer(
                f"Введите новое <b>{field_labels.get(field, field)}</b>:", parse_mode='html'
            )
        return

    # ── Редактирование: выбор бухгалтера ─────────────────────────────────────
    if payload.startswith('edit_acc:'):
        acc_id_str = payload.split(':', 1)[1]
        acc_id = int(acc_id_str) if acc_id_str != '0' else None
        data = st.storage.get_data(user_id)
        co_id = data.get('edit_company_id')
        if co_id:
            await run_db(db.update_company, co_id, accountant_id=acc_id)
            st.storage.clear(user_id)
            await callback.message.answer("✅ Бухгалтер обновлён.")
        return

    # ── Деактивация компании ──────────────────────────────────────────────────
    if payload.startswith('deactivate:'):
        co_id = int(payload.split(':', 1)[1])
        company = await run_db(db.get_company, co_id)
        await callback.message.answer(
            f"Деактивировать <b>{company['name']}</b>?\nДанные сохранятся.",
            parse_mode='html',
            attachments=[kb.confirm_keyboard(f'confirm_deactivate:{co_id}')]
        )
        return

    if payload.startswith('confirm_deactivate:'):
        co_id = int(payload.split(':', 1)[1])
        company = await run_db(db.get_company, co_id)
        await run_db(db.deactivate_company, co_id)
        st.storage.clear(user_id)
        await callback.message.answer(
            f"🗑 <b>{company['name']}</b> деактивирована.", parse_mode='html'
        )
        return

    # ── Ошибка: выбор бухгалтера ──────────────────────────────────────────────
    if payload.startswith('err_acc:'):
        acc_id = int(payload.split(':', 1)[1])
        companies = await run_db(db.get_all_companies)
        st.storage.update(user_id, err_accountant_id=acc_id)
        st.storage.set(user_id, st.ADD_ERR_COMPANY, **st.storage.get_data(user_id))
        await callback.message.answer(
            "Выберите компанию (или «Без компании»):",
            attachments=[kb.companies_keyboard(companies, 'err_co')]
        )
        return

    # ── Ошибка: выбор компании ────────────────────────────────────────────────
    if payload.startswith('err_co:'):
        co_id = int(payload.split(':', 1)[1])
        st.storage.update(user_id, err_company_id=co_id)
        st.storage.set(user_id, st.ADD_ERR_DESC, **st.storage.get_data(user_id))
        await callback.message.answer("Опишите ошибку:")
        return

    # ── Карточка компании ─────────────────────────────────────────────────────
    if payload.startswith('info_co:'):
        co_id = int(payload.split(':', 1)[1])
        company = await run_db(db.get_company, co_id)
        if not company:
            await callback.message.answer("Компания не найдена."); return
        dls = await run_db(db.get_deadlines_for_company, co_id, 'pending')
        upcoming = sorted(
            [d for d in dls if days_left(d['due_date']) >= 0], key=lambda x: x['due_date']
        )[:5]
        lines = [
            f"🏢 <b>{company['name']}</b>\n",
            f"ИНН: {company['inn'] or '—'}",
            f"Система: {company['tax_system']} | {company['org_type'] or '—'}",
            f"Сотрудники: {'Да' if company['has_employees'] else 'Нет'} | "
            f"Воинский учёт: {'Да' if company['has_military'] else 'Нет'}",
            f"Бухгалтер: {company['accountant_name'] or '—'}",
            f"Max-группа: {company['max_group_id'] or 'не привязана'}",
            f"\n📋 <b>Стандарт работы:</b>\n{company['work_standard'] or '— не заполнен —'}",
        ]
        if upcoming:
            lines.append("\n📅 <b>Ближайшие дедлайны:</b>")
            for dl in upcoming:
                emoji = deadline_emoji(dl['due_date'], dl['status'])
                lines.append(f"{emoji} {fmt_date(dl['due_date'])} — {dl['report_name']}")
        await callback.message.answer('\n'.join(lines), parse_mode='html')
        return


# ─── Вспомогательные async-функции ────────────────────────────────────────────

async def _ask_accountant(event_or_callback, user_id: str):
    accs = await run_db(db.get_all_accountants)
    await event_or_callback.message.answer(
        "Шаг 8/9. Назначьте <b>бухгалтера</b>:",
        parse_mode='html', attachments=[kb.accountants_keyboard(accs)]
    )


async def _save_company(event_or_callback, user_id: str):
    data = st.storage.get_data(user_id)
    company_id = await run_db(
        db.add_company,
        data.get('name', ''),
        data.get('inn'),
        data.get('tax_system', 'УСН'),
        data.get('org_type', 'ООО'),
        data.get('has_employees', False),
        data.get('has_military', False),
        data.get('max_group_id'),
        data.get('accountant_id'),
        data.get('work_standard'),
    )
    st.storage.clear(user_id)
    d = data
    await event_or_callback.message.answer(
        f"✅ <b>Компания добавлена!</b>\n\n"
        f"🏢 {d.get('name')} | {d.get('tax_system')} | {d.get('org_type', 'ООО')}\n"
        f"ИНН: {d.get('inn') or '—'} | Сотрудники: {'Да' if d.get('has_employees') else 'Нет'}\n"
        f"Стандарт: {'✅ заполнен' if d.get('work_standard') else '— не заполнен'}\n\n"
        f"Создать <b>календарь отчётности</b>?",
        parse_mode='html',
        attachments=[kb.gen_deadlines_keyboard(company_id)]
    )


async def _save_work(event_or_callback, user_id: str, work_date: str):
    data = st.storage.get_data(user_id)
    work_id = await run_db(
        db.add_additional_work,
        data['company_id'], data['description'], data['work_type'],
        work_date, data.get('accountant_id'), data.get('hours', 0), data.get('amount', 0)
    )
    st.storage.clear(user_id)
    await event_or_callback.message.answer(
        f"✅ Доп. работа зафиксирована (#{work_id})! Войдёт в отчёт за месяц."
    )


async def _save_deadline(event_or_callback, user_id: str, period: str = None):
    data = st.storage.get_data(user_id)
    dl_id = await run_db(
        db.add_deadline,
        data['company_id'], data['dl_name'],
        data.get('dl_type', 'Иное'), data['dl_date'], period
    )
    st.storage.clear(user_id)
    await event_or_callback.message.answer(
        f"✅ Дедлайн добавлен (#{dl_id})!\n"
        f"<b>{data['dl_name']}</b> — {fmt_date(data['dl_date'])}",
        parse_mode='html'
    )


async def _save_error(event_or_callback, user_id: str, err_date: str):
    data = st.storage.get_data(user_id)
    err_id = await run_db(
        db.add_error,
        data['err_accountant_id'], data['err_description'],
        err_date, data.get('err_company_id')
    )
    st.storage.clear(user_id)
    await event_or_callback.message.answer(
        f"⚠️ Ошибка зафиксирована (#{err_id}). Войдёт в KPI за месяц."
    )


async def _send_accountant_deadlines(event_or_callback, acc):
    companies = await run_db(db.get_companies_by_accountant, acc['id'])
    all_deadlines = []
    for co in companies:
        dls = await run_db(db.get_deadlines_for_company, co['id'], 'pending')
        for dl in dls:
            if days_left(dl['due_date']) >= 0:
                all_deadlines.append((co['name'], dl))
    all_deadlines.sort(key=lambda x: x[1]['due_date'])
    if not all_deadlines:
        await event_or_callback.message.answer("✅ Нет ближайших дедлайнов!")
        return
    lines = ["📅 <b>Ваши ближайшие дедлайны:</b>\n"]
    for co_name, dl in all_deadlines[:20]:
        emoji = deadline_emoji(dl['due_date'], dl['status'])
        lines.append(
            f"{emoji} {fmt_date(dl['due_date'])} | <b>{co_name}</b>\n"
            f"    {dl['report_name']} ({days_left(dl['due_date'])} дн.)"
        )
    flat_dls = [x[1] for x in all_deadlines[:10]]
    await event_or_callback.message.answer(
        '\n'.join(lines), parse_mode='html',
        attachments=[kb.deadlines_keyboard(flat_dls)]
    )


# ─── Функции меню руководителя ────────────────────────────────────────────────

async def _show_companies(callback: MessageCallback):
    companies = await run_db(db.get_all_companies)
    if not companies:
        await callback.message.answer("Компаний нет. Добавьте: /add_company"); return
    lines = ["🏢 <b>Список компаний:</b>\n"]
    for c in companies:
        acc = c['accountant_name'] or 'не назначен'
        lines.append(f"• <b>{c['name']}</b> | {c['tax_system']} | {c['org_type'] or '—'} | 👤 {acc}")
    lines.append(f"\nВсего: {len(companies)}")
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _show_accountants(callback: MessageCallback):
    accs = await run_db(db.get_all_accountants)
    if not accs:
        await callback.message.answer("Бухгалтеры не добавлены: /add_accountant"); return
    lines = ["👤 <b>Бухгалтеры:</b>\n"]
    for a in accs:
        lines.append(f"• {a['name']} | Max ID: {a['max_user_id'] or 'не указан'}")
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _show_upcoming(callback: MessageCallback):
    deadlines = await run_db(db.get_upcoming_deadlines, 30)
    if not deadlines:
        await callback.message.answer("✅ На 30 дней дедлайнов нет."); return
    lines = ["📅 <b>Дедлайны на 30 дней:</b>\n"]
    for dl in deadlines[:30]:
        emoji = deadline_emoji(dl['due_date'], dl['status'])
        acc = dl['accountant_name'] or '—'
        lines.append(
            f"{emoji} {fmt_date(dl['due_date'])} | {dl['company_name']}\n"
            f"    {dl['report_name']} | {acc} | {days_left(dl['due_date'])} дн."
        )
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _show_overdue(callback: MessageCallback):
    deadlines = await run_db(db.get_overdue_deadlines)
    if not deadlines:
        await callback.message.answer("✅ Просроченных дедлайнов нет!"); return
    lines = ["🔴 <b>Просроченные дедлайны:</b>\n"]
    for dl in deadlines[:30]:
        acc = dl['accountant_name'] or '—'
        lines.append(
            f"🔴 {fmt_date(dl['due_date'])} | {dl['company_name']}\n"
            f"    {dl['report_name']} | {acc} | просрочено {abs(days_left(dl['due_date']))} дн."
        )
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _show_monthly_report(callback: MessageCallback):
    now = datetime.now()
    works = await run_db(db.get_additional_works_for_month, now.year, now.month)
    if not works:
        await callback.message.answer(
            f"📊 Доп. работ за {now.strftime('%m.%Y')} не зафиксировано."
        ); return
    by_company: dict = {}
    total_hours = total_amount = 0.0
    for w in works:
        co = w['company_name']
        by_company.setdefault(co, []).append(w)
        total_hours += w['hours'] or 0
        total_amount += w['amount'] or 0
    lines = [f"📊 <b>Доп. работы за {now.strftime('%m.%Y')}:</b>\n"]
    for co_name, ws in by_company.items():
        co_h = sum(w['hours'] or 0 for w in ws)
        co_a = sum(w['amount'] or 0 for w in ws)
        lines.append(f"\n🏢 <b>{co_name}</b>")
        for w in ws:
            acc = w['accountant_name'] or '—'
            lines.append(
                f"  • {fmt_date(w['work_date'])} | {w['work_type']}\n"
                f"    {w['description'][:50]} | {w['hours']}ч | {w['amount']:,.0f}₽ | {acc}"
            )
        lines.append(f"  Итого: {co_h}ч / {co_a:,.0f}₽")
    lines.append(f"\n📌 <b>ИТОГО: {total_hours}ч / {total_amount:,.0f}₽</b>")
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _send_excel_report(callback: MessageCallback):
    """
    Генерирует Excel и сохраняет на диск.
    Прямая отправка файла через maxapi не задокументирована —
    уведомляем о пути к файлу, текстовый отчёт как fallback.
    TODO: заменить на отправку файла когда будет подтверждён API.
    """
    await callback.message.answer("⏳ Формирую Excel-отчёт...")
    try:
        filepath = await asyncio.to_thread(excel_report.generate_monthly_report)
        filename = filepath.replace('\\', '/').split('/')[-1]
        await callback.message.answer(
            f"📊 Excel-отчёт сформирован!\n"
            f"📁 Файл: <code>{filepath}</code>\n\n"
            f"Скачайте с сервера или используйте текстовый отчёт:\n"
            f"Меню → 📊 Отчёт за месяц (текст)",
            parse_mode='html'
        )
    except Exception as e:
        logger.error(f"Ошибка генерации Excel: {e}")
        await callback.message.answer(f"❌ Ошибка: {e}")


async def _show_kpi(callback: MessageCallback):
    """KPI с реальными ошибками (get_accountant_stats_full)."""
    now = datetime.now()
    stats = await run_db(db.get_accountant_stats_full, now.year, now.month)
    if not stats:
        await callback.message.answer("Данных для KPI нет."); return
    lines = [f"📈 <b>KPI бухгалтеров за {now.strftime('%m.%Y')}:</b>\n"]
    for s in stats:
        total = s['total_deadlines'] or 0
        done = s['done_deadlines'] or 0
        overdue = s['overdue_deadlines'] or 0
        errors = s['error_count'] or 0
        pct = round(done / total * 100) if total > 0 else 0
        err_pct = round(errors / total * 100, 1) if total > 0 else 0
        lines.append(
            f"👤 <b>{s['name']}</b>\n"
            f"  🏢 Компаний: {s['company_count'] or 0}\n"
            f"  📄 Дедлайнов: {total} | ✅ {done} | 🔴 {overdue}\n"
            f"  📊 Исполнение: {pct}% | ⚠️ Ошибок: {errors} ({err_pct}%)\n"
            f"  ➕ Доп.работы: {s['extra_hours'] or 0}ч / {(s['extra_amount'] or 0):,.0f}₽"
        )
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _show_errors_log(callback: MessageCallback):
    now = datetime.now()
    errors = await run_db(db.get_errors_for_month, now.year, now.month)
    if not errors:
        await callback.message.answer(f"✅ Ошибок за {now.strftime('%m.%Y')} не зафиксировано."); return
    lines = [f"⚠️ <b>Журнал ошибок за {now.strftime('%m.%Y')}:</b>\n"]
    for e in errors:
        co = e['company_name'] or '—'
        lines.append(
            f"• {fmt_date(e['error_date'])} | <b>{e['accountant_name']}</b>\n"
            f"  🏢 {co}\n  📝 {e['description']}"
        )
    await callback.message.answer('\n'.join(lines), parse_mode='html')


async def _handle_acc_menu(callback: MessageCallback, payload: str, user_id: str):
    action = payload.split(':', 1)[1]
    acc = await run_db(db.get_accountant_by_user_id, user_id)

    if action == 'tasks':
        if not acc:
            await callback.message.answer("Вы не зарегистрированы."); return
        tasks = await run_db(db.get_tasks_for_accountant, acc['id'], 'pending')
        if not tasks:
            await callback.message.answer("✅ Нет активных задач!"); return
        lines = ["📋 <b>Ваши задачи:</b>\n"]
        for t in tasks:
            due = fmt_date(t['due_date']) if t['due_date'] else '—'
            lines.append(f"#{t['id']} | {t['title']}\n  🏢 {t['company_name'] or '—'} | 📅 {due}")
        await callback.message.answer(
            '\n'.join(lines), parse_mode='html', attachments=[kb.tasks_keyboard(tasks)]
        )

    elif action == 'deadlines':
        if not acc:
            await callback.message.answer("Вы не зарегистрированы."); return
        await _send_accountant_deadlines(callback, acc)

    elif action == 'mark_done':
        if not acc:
            await callback.message.answer("Вы не зарегистрированы."); return
        companies = await run_db(db.get_companies_by_accountant, acc['id'])
        all_dls = []
        for co in companies:
            dls = await run_db(db.get_deadlines_for_company, co['id'], 'pending')
            all_dls.extend([d for d in dls if days_left(d['due_date']) >= -7])
        all_dls.sort(key=lambda x: x['due_date'])
        if not all_dls:
            await callback.message.answer("Нет активных дедлайнов."); return
        await callback.message.answer(
            "Выберите дедлайн для отметки:",
            attachments=[kb.deadlines_keyboard(all_dls)]
        )

    elif action == 'add_work':
        # Исправлен: отдельные вызовы вместо тернарного run_db
        if acc:
            companies = await run_db(db.get_companies_by_accountant, acc['id'])
        else:
            companies = await run_db(db.get_all_companies)
        if not companies:
            await callback.message.answer("Нет доступных компаний."); return
        st.storage.set(user_id, st.ADD_WORK_COMPANY,
                       accountant_id=acc['id'] if acc else None)
        await callback.message.answer(
            "Выберите компанию:",
            attachments=[kb.companies_keyboard(companies, 'work_co')]
        )
