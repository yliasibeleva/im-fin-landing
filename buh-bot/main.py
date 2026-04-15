"""
Точка входа. Инициализирует БД, регистрирует handlers, запускает планировщик и polling.
"""
import asyncio
import logging

from maxapi import Bot

from config import BOT_TOKEN
import database as db
from handlers import dp
from reminders import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error(
            "BOT_TOKEN не задан! Скопируйте .env.example в .env и заполните токен."
        )
        return

    # Инициализируем базу данных
    logger.info("Инициализация базы данных...")
    db.init_db()
    logger.info("База данных готова.")

    # Создаём бота
    bot = Bot(BOT_TOKEN)

    # Запускаем планировщик напоминаний
    scheduler = start_scheduler(bot)

    logger.info("Бот запущен. Ожидание сообщений...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        logger.info("Бот остановлен.")


if __name__ == '__main__':
    asyncio.run(main())
