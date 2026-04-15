"""
Планировщик напоминаний.
Каждый день в заданное время проверяет дедлайны и отправляет уведомления:
  - в группу клиента (Max group)
  - бухгалтеру (личное сообщение)
  - в список ADMIN_IDS (сводка просроченных)
"""
import asyncio
import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from maxapi import Bot

import database as db
from config import ADMIN_IDS, REMINDER_HOUR, REMINDER_DAYS, TIMEZONE, ACCOUNTANTS_GROUP_ID, MANAGERS_GROUP_ID

logger = logging.getLogger(__name__)


def days_until(iso_date: str) -> int:
    try:
        d = date.fromisoformat(iso_date[:10])
        return (d - date.today()).days
    except ValueError:
        return 999


def fmt_date(iso_date: str) -> str:
    try:
        d = date.fromisoformat(iso_date[:10])
        return d.strftime('%d.%m.%Y')
    except ValueError:
        return iso_date


async def send_safe(bot: Bot, chat_id, text: str):
    """Отправляет сообщение, не падая при ошибке."""
    try:
        await bot.send_message(chat_id=int(chat_id), text=text, parse_mode='html')
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение в {chat_id}: {e}")


async def run_daily_check(bot: Bot):
    """Основная задача: проверить дедлайны и разослать напоминания."""
    logger.info("Запуск ежедневной проверки дедлайнов...")

    deadlines = await asyncio.to_thread(db.get_upcoming_deadlines, max(REMINDER_DAYS) + 1)

    # Шаг 1: определяем все дедлайны к напоминанию сегодня
    to_notify = []  # list of (deadline_dict, days_before)
    for dl in deadlines:
        dl_days = days_until(dl['due_date'])
        if dl_days not in REMINDER_DAYS:
            continue
        already_sent = await asyncio.to_thread(db.was_reminder_sent, dl['id'], dl_days)
        if not already_sent:
            to_notify.append((dl, dl_days))

    # Шаг 2: группируем по получателям — одно сообщение на группу/бухгалтера
    by_group: dict = {}    # group_id → [(dl, days_before)]
    by_acc: dict = {}      # acc_max_id → [(dl, days_before)]

    for dl, days_before in to_notify:
        group_id = dl.get('max_group_id')
        if group_id:
            by_group.setdefault(group_id, []).append((dl, days_before))

        acc_max_id = dl.get('accountant_max_id')
        if acc_max_id:
            by_acc.setdefault(acc_max_id, []).append((dl, days_before))

    # Шаг 3: отправляем в группы клиентов (одно сообщение со всеми дедлайнами)
    for group_id, items in by_group.items():
        lines = ["📅 <b>Напоминание об отчётности</b>\n"]
        for dl, days_before in items:
            if days_before == 0:
                urgency = "🔴 <b>СЕГОДНЯ последний день!</b>"
            elif days_before == 1:
                urgency = "🟠 <b>ЗАВТРА последний день!</b>"
            elif days_before <= 3:
                urgency = f"🟠 Осталось <b>{days_before} дня</b>"
            else:
                urgency = f"🟡 Осталось <b>{days_before} дней</b>"
            lines.append(
                f"\n{urgency}\n"
                f"📄 {dl['report_name']}\n"
                f"🗓 Срок: {fmt_date(dl['due_date'])}"
            )
        await send_safe(bot, group_id, '\n'.join(lines))

    # Шаг 4: отправляем бухгалтерам (одна сводка со всеми их дедлайнами)
    for acc_max_id, items in by_acc.items():
        lines = ["📅 <b>Дедлайны на контроле сегодня:</b>\n"]
        for dl, days_before in items:
            emoji = '🔴' if days_before <= 1 else ('🟠' if days_before <= 3 else '🟡')
            lines.append(
                f"{emoji} <b>{dl['company_name']}</b>\n"
                f"   {dl['report_name']}\n"
                f"   🗓 {fmt_date(dl['due_date'])} ({days_before} дн.)"
            )
        lines.append("\nОтметьте выполнение: /mydeadlines")
        await send_safe(bot, acc_max_id, '\n'.join(lines))

    # Шаг 5: логируем все отправленные напоминания
    for dl, days_before in to_notify:
        await asyncio.to_thread(db.log_reminder, dl['id'], days_before)

    logger.info(f"Напоминания отправлены: {len(to_notify)} дедлайнов, "
                f"{len(by_group)} групп клиентов, {len(by_acc)} бухгалтеров.")

    # ── Сводка просроченных для администраторов и группы бухгалтеров ──────────
    overdue = await asyncio.to_thread(db.get_overdue_deadlines)
    if overdue:
        lines = [f"🔴 <b>Просроченные дедлайны ({date.today().strftime('%d.%m.%Y')}):</b>\n"]
        for dl in overdue[:20]:
            days_over = abs(days_until(dl['due_date']))
            acc = dl['accountant_name'] or '—'
            lines.append(
                f"• {dl['company_name']} | {dl['report_name']}\n"
                f"  Срок: {fmt_date(dl['due_date'])} | Просрочено {days_over} дн. | {acc}"
            )
        overdue_text = '\n'.join(lines)

        # Администраторам (в личку)
        for admin_id in ADMIN_IDS:
            await send_safe(bot, admin_id, overdue_text)

        # В группу бухгалтеров
        if ACCOUNTANTS_GROUP_ID:
            await send_safe(bot, ACCOUNTANTS_GROUP_ID, overdue_text)

        # В группу руководителей (если отдельная)
        if MANAGERS_GROUP_ID and MANAGERS_GROUP_ID != ACCOUNTANTS_GROUP_ID:
            await send_safe(bot, MANAGERS_GROUP_ID, overdue_text)

    # ── Утренняя сводка предстоящих дедлайнов для группы бухгалтеров ─────────
    if ACCOUNTANTS_GROUP_ID:
        upcoming_7 = await asyncio.to_thread(db.get_upcoming_deadlines, 7)
        if upcoming_7:
            lines = [f"📅 <b>Дедлайны на 7 дней ({date.today().strftime('%d.%m.%Y')}):</b>\n"]
            for dl in upcoming_7[:15]:
                dl_days = days_until(dl['due_date'])
                emoji = '🔴' if dl_days <= 1 else ('🟠' if dl_days <= 3 else '🟡')
                acc = dl['accountant_name'] or '—'
                lines.append(
                    f"{emoji} {fmt_date(dl['due_date'])} | {dl['company_name']}\n"
                    f"    {dl['report_name']} | {acc} | {dl_days} дн."
                )
            await send_safe(bot, ACCOUNTANTS_GROUP_ID, '\n'.join(lines))

    logger.info(f"Проверка завершена. Дедлайнов в окне: {len(deadlines)}")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Создаёт и запускает планировщик."""
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        run_daily_check,
        trigger=CronTrigger(hour=REMINDER_HOUR, minute=0, timezone=tz),
        args=[bot],
        id='daily_reminder',
        name='Ежедневная рассылка напоминаний',
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"Планировщик запущен. Напоминания отправляются в {REMINDER_HOUR}:00 МСК. "
        f"Дни до дедлайна: {REMINDER_DAYS}"
    )
    return scheduler
