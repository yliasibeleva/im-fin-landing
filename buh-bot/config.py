import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')

_admin_raw = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = [x.strip() for x in _admin_raw.split(',') if x.strip()]

DB_PATH = os.getenv('DB_PATH', 'data_storage/buh_bot.db')

REMINDER_HOUR = int(os.getenv('REMINDER_HOUR', '9'))

_days_raw = os.getenv('REMINDER_DAYS', '14,7,3,1')
REMINDER_DAYS = [int(x.strip()) for x in _days_raw.split(',') if x.strip()]

TIMEZONE = 'Europe/Moscow'

ACCOUNTANTS_GROUP_ID = os.getenv('ACCOUNTANTS_GROUP_ID', '').strip() or None
MANAGERS_GROUP_ID = os.getenv('MANAGERS_GROUP_ID', '').strip() or None
