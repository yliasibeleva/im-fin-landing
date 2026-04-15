"""
База данных: схема + все CRUD-операции.
Используется синхронный sqlite3, вызовы из async-кода идут через asyncio.to_thread.
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional

from config import DB_PATH


# ─── Инициализация ────────────────────────────────────────────────────────────

def init_db() -> None:
    dir_path = os.path.dirname(DB_PATH)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS accountants (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                max_user_id   TEXT UNIQUE,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS companies (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                inn             TEXT,
                tax_system      TEXT NOT NULL,
                org_type        TEXT DEFAULT 'ООО',
                has_employees   INTEGER DEFAULT 0,
                has_military    INTEGER DEFAULT 0,
                max_group_id    TEXT,
                accountant_id   INTEGER REFERENCES accountants(id),
                work_standard   TEXT,
                notes           TEXT,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS accountant_errors (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                accountant_id INTEGER NOT NULL REFERENCES accountants(id),
                company_id    INTEGER REFERENCES companies(id),
                description   TEXT NOT NULL,
                error_date    TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS report_deadlines (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id    INTEGER NOT NULL REFERENCES companies(id),
                report_name   TEXT NOT NULL,
                report_type   TEXT NOT NULL,
                due_date      TEXT NOT NULL,            -- ISO date YYYY-MM-DD
                period        TEXT,                     -- Q1/2025, 2025 год и т.п.
                status        TEXT DEFAULT 'pending',   -- pending / done / overdue
                completed_at  TEXT,
                notes         TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reminder_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                deadline_id   INTEGER NOT NULL REFERENCES report_deadlines(id),
                days_before   INTEGER,
                sent_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id    INTEGER REFERENCES companies(id),
                accountant_id INTEGER REFERENCES accountants(id),
                title         TEXT NOT NULL,
                description   TEXT,
                due_date      TEXT,
                status        TEXT DEFAULT 'pending',   -- pending / in_progress / done / overdue
                priority      TEXT DEFAULT 'normal',    -- low / normal / high
                created_at    TEXT DEFAULT (datetime('now')),
                completed_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS additional_works (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id    INTEGER NOT NULL REFERENCES companies(id),
                accountant_id INTEGER REFERENCES accountants(id),
                description   TEXT NOT NULL,
                work_type     TEXT NOT NULL,
                hours         REAL DEFAULT 0,
                work_date     TEXT NOT NULL,
                amount        REAL DEFAULT 0,
                created_at    TEXT DEFAULT (datetime('now'))
            );
        """)
        # Миграция: добавляем колонки если БД уже существовала без них
        _migrate(conn)


def _migrate(conn) -> None:
    """Добавляет новые колонки в существующую БД (безопасно)."""
    migrations = [
        "ALTER TABLE companies ADD COLUMN work_standard TEXT",
        "ALTER TABLE companies ADD COLUMN org_type TEXT DEFAULT 'ООО'",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass  # Колонка уже есть — игнорируем


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Бухгалтеры ───────────────────────────────────────────────────────────────

def add_accountant(name: str, max_user_id: str = None) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO accountants (name, max_user_id) VALUES (?, ?)",
            (name, max_user_id)
        )
        return cur.lastrowid


def get_all_accountants() -> list:
    with get_db() as conn:
        return conn.execute("SELECT * FROM accountants ORDER BY name").fetchall()


def get_accountant_by_user_id(max_user_id: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM accountants WHERE max_user_id = ?", (str(max_user_id),)
        ).fetchone()


def get_accountant(accountant_id: int):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM accountants WHERE id = ?", (accountant_id,)
        ).fetchone()


# ─── Компании ─────────────────────────────────────────────────────────────────

def add_company(
    name: str,
    inn: str,
    tax_system: str,
    org_type: str,
    has_employees: bool,
    has_military: bool,
    max_group_id: str = None,
    accountant_id: int = None,
    work_standard: str = None,
    notes: str = None
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO companies
               (name, inn, tax_system, org_type, has_employees, has_military,
                max_group_id, accountant_id, work_standard, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, inn, tax_system, org_type,
             int(has_employees), int(has_military),
             max_group_id, accountant_id, work_standard, notes)
        )
        return cur.lastrowid


def get_all_companies(active_only: bool = True) -> list:
    with get_db() as conn:
        q = "SELECT c.*, a.name as accountant_name FROM companies c LEFT JOIN accountants a ON c.accountant_id = a.id"
        if active_only:
            q += " WHERE c.is_active = 1"
        q += " ORDER BY c.name"
        return conn.execute(q).fetchall()


def get_company(company_id: int):
    with get_db() as conn:
        return conn.execute(
            """SELECT c.*, a.name as accountant_name
               FROM companies c LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE c.id = ?""",
            (company_id,)
        ).fetchone()


def get_companies_by_accountant(accountant_id: int) -> list:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM companies WHERE accountant_id = ? AND is_active = 1 ORDER BY name",
            (accountant_id,)
        ).fetchall()


def get_company_by_group_id(max_group_id: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM companies WHERE max_group_id = ? AND is_active = 1",
            (str(max_group_id),)
        ).fetchone()


def update_company_group(company_id: int, max_group_id: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE companies SET max_group_id = ? WHERE id = ?",
            (max_group_id, company_id)
        )


# ─── Дедлайны ─────────────────────────────────────────────────────────────────

def add_deadline(
    company_id: int,
    report_name: str,
    report_type: str,
    due_date: str,  # YYYY-MM-DD
    period: str = None
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO report_deadlines
               (company_id, report_name, report_type, due_date, period)
               VALUES (?, ?, ?, ?, ?)""",
            (company_id, report_name, report_type, due_date, period)
        )
        return cur.lastrowid


def add_deadlines_bulk(deadlines: list) -> None:
    with get_db() as conn:
        conn.executemany(
            """INSERT INTO report_deadlines
               (company_id, report_name, report_type, due_date, period)
               VALUES (:company_id, :report_name, :report_type, :due_date, :period)""",
            deadlines
        )


def get_deadlines_for_company(company_id: int, status: str = None) -> list:
    with get_db() as conn:
        q = "SELECT * FROM report_deadlines WHERE company_id = ?"
        params = [company_id]
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY due_date"
        return conn.execute(q, params).fetchall()


def get_upcoming_deadlines(days_ahead: int = 30) -> list:
    """Все дедлайны на ближайшие N дней (pending)."""
    from datetime import timedelta
    today = date.today().isoformat()
    future_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    with get_db() as conn:
        return conn.execute(
            """SELECT rd.*, c.name as company_name, c.max_group_id,
                      a.name as accountant_name, a.max_user_id as accountant_max_id
               FROM report_deadlines rd
               JOIN companies c ON rd.company_id = c.id
               LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE rd.status = 'pending'
                 AND rd.due_date BETWEEN ? AND ?
                 AND c.is_active = 1
               ORDER BY rd.due_date""",
            (today, future_date)
        ).fetchall()


def get_overdue_deadlines() -> list:
    today = date.today().isoformat()
    with get_db() as conn:
        return conn.execute(
            """SELECT rd.*, c.name as company_name,
                      a.name as accountant_name, a.max_user_id as accountant_max_id
               FROM report_deadlines rd
               JOIN companies c ON rd.company_id = c.id
               LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE rd.status = 'pending'
                 AND rd.due_date < ?
                 AND c.is_active = 1
               ORDER BY rd.due_date""",
            (today,)
        ).fetchall()


def mark_deadline_done(deadline_id: int) -> None:
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE report_deadlines SET status = 'done', completed_at = ? WHERE id = ?",
            (now, deadline_id)
        )


def get_deadline(deadline_id: int):
    with get_db() as conn:
        return conn.execute(
            "SELECT rd.*, c.name as company_name FROM report_deadlines rd JOIN companies c ON rd.company_id = c.id WHERE rd.id = ?",
            (deadline_id,)
        ).fetchone()


# ─── Логи напоминаний ─────────────────────────────────────────────────────────

def was_reminder_sent(deadline_id: int, days_before: int) -> bool:
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM reminder_logs
               WHERE deadline_id = ? AND days_before = ?
                 AND sent_at >= ?""",
            (deadline_id, days_before, today + ' 00:00:00')
        ).fetchone()
        return row is not None


def log_reminder(deadline_id: int, days_before: int) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reminder_logs (deadline_id, days_before) VALUES (?, ?)",
            (deadline_id, days_before)
        )


# ─── Задачи ───────────────────────────────────────────────────────────────────

def add_task(
    title: str,
    company_id: int = None,
    accountant_id: int = None,
    description: str = None,
    due_date: str = None,
    priority: str = 'normal'
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO tasks
               (company_id, accountant_id, title, description, due_date, priority)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, accountant_id, title, description, due_date, priority)
        )
        return cur.lastrowid


def get_tasks_for_accountant(accountant_id: int, status: str = None) -> list:
    with get_db() as conn:
        q = """SELECT t.*, c.name as company_name
               FROM tasks t LEFT JOIN companies c ON t.company_id = c.id
               WHERE t.accountant_id = ?"""
        params = [accountant_id]
        if status:
            q += " AND t.status = ?"
            params.append(status)
        q += " ORDER BY t.due_date NULLS LAST, t.created_at"
        return conn.execute(q, params).fetchall()


def get_all_tasks(status: str = None) -> list:
    with get_db() as conn:
        q = """SELECT t.*, c.name as company_name, a.name as accountant_name
               FROM tasks t
               LEFT JOIN companies c ON t.company_id = c.id
               LEFT JOIN accountants a ON t.accountant_id = a.id"""
        if status:
            q += " WHERE t.status = ?"
            return conn.execute(q, (status,)).fetchall()
        return conn.execute(q).fetchall()


def mark_task_done(task_id: int) -> None:
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
            (now, task_id)
        )


def get_task(task_id: int):
    with get_db() as conn:
        return conn.execute(
            """SELECT t.*, c.name as company_name, a.name as accountant_name
               FROM tasks t
               LEFT JOIN companies c ON t.company_id = c.id
               LEFT JOIN accountants a ON t.accountant_id = a.id
               WHERE t.id = ?""",
            (task_id,)
        ).fetchone()


# ─── Доп. работы ──────────────────────────────────────────────────────────────

def add_additional_work(
    company_id: int,
    description: str,
    work_type: str,
    work_date: str,
    accountant_id: int = None,
    hours: float = 0,
    amount: float = 0
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO additional_works
               (company_id, accountant_id, description, work_type, hours, work_date, amount)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_id, accountant_id, description, work_type, hours, work_date, amount)
        )
        return cur.lastrowid


def get_additional_works_for_month(year: int, month: int) -> list:
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year+1}-01-01"
    else:
        end = f"{year}-{month+1:02d}-01"
    with get_db() as conn:
        return conn.execute(
            """SELECT aw.*, c.name as company_name, a.name as accountant_name
               FROM additional_works aw
               JOIN companies c ON aw.company_id = c.id
               LEFT JOIN accountants a ON aw.accountant_id = a.id
               WHERE aw.work_date >= ? AND aw.work_date < ?
               ORDER BY c.name, aw.work_date""",
            (start, end)
        ).fetchall()


def get_additional_works_for_company_month(company_id: int, year: int, month: int) -> list:
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    with get_db() as conn:
        return conn.execute(
            """SELECT aw.*, a.name as accountant_name
               FROM additional_works aw
               LEFT JOIN accountants a ON aw.accountant_id = a.id
               WHERE aw.company_id = ? AND aw.work_date >= ? AND aw.work_date < ?
               ORDER BY aw.work_date""",
            (company_id, start, end)
        ).fetchall()


# ─── Статистика для руководителя ──────────────────────────────────────────────

def get_accountant_stats(year: int, month: int) -> list:
    """KPI по каждому бухгалтеру за месяц."""
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    with get_db() as conn:
        return conn.execute(
            """SELECT
                a.id, a.name,
                COUNT(DISTINCT c.id) as company_count,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id
                   AND rd.due_date >= ? AND rd.due_date < ?) as total_deadlines,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id AND rd.status = 'done'
                   AND rd.due_date >= ? AND rd.due_date < ?) as done_deadlines,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id AND rd.status = 'overdue'
                   AND rd.due_date >= ? AND rd.due_date < ?) as overdue_deadlines,
                (SELECT COALESCE(SUM(aw.hours),0) FROM additional_works aw
                 WHERE aw.accountant_id = a.id
                   AND aw.work_date >= ? AND aw.work_date < ?) as extra_hours,
                (SELECT COALESCE(SUM(aw.amount),0) FROM additional_works aw
                 WHERE aw.accountant_id = a.id
                   AND aw.work_date >= ? AND aw.work_date < ?) as extra_amount
               FROM accountants a
               LEFT JOIN companies c ON c.accountant_id = a.id AND c.is_active = 1
               GROUP BY a.id, a.name
               ORDER BY a.name""",
            (start, end, start, end, start, end, start, end, start, end)
        ).fetchall()


# ─── Обновление компании ──────────────────────────────────────────────────────

def update_company(company_id: int, **fields) -> None:
    """Обновляет произвольные поля компании."""
    allowed = {
        'name', 'inn', 'tax_system', 'org_type', 'has_employees',
        'has_military', 'max_group_id', 'accountant_id', 'work_standard',
        'notes', 'is_active'
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [company_id]
    with get_db() as conn:
        conn.execute(f"UPDATE companies SET {set_clause} WHERE id = ?", values)


def deactivate_company(company_id: int) -> None:
    with get_db() as conn:
        conn.execute("UPDATE companies SET is_active = 0 WHERE id = ?", (company_id,))


# ─── Ошибки бухгалтеров ───────────────────────────────────────────────────────

def add_error(
    accountant_id: int,
    description: str,
    error_date: str,
    company_id: int = None
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO accountant_errors
               (accountant_id, company_id, description, error_date)
               VALUES (?, ?, ?, ?)""",
            (accountant_id, company_id, description, error_date)
        )
        return cur.lastrowid


def get_errors_for_month(year: int, month: int) -> list:
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    with get_db() as conn:
        return conn.execute(
            """SELECT ae.*, a.name as accountant_name, c.name as company_name
               FROM accountant_errors ae
               JOIN accountants a ON ae.accountant_id = a.id
               LEFT JOIN companies c ON ae.company_id = c.id
               WHERE ae.error_date >= ? AND ae.error_date < ?
               ORDER BY a.name, ae.error_date""",
            (start, end)
        ).fetchall()


def get_error_count_for_accountant(accountant_id: int, year: int, month: int) -> int:
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    with get_db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) FROM accountant_errors
               WHERE accountant_id = ? AND error_date >= ? AND error_date < ?""",
            (accountant_id, start, end)
        ).fetchone()
        return row[0] if row else 0


# ─── Обновлённая статистика с ошибками ───────────────────────────────────────

def get_accountant_stats_full(year: int, month: int) -> list:
    """KPI по каждому бухгалтеру за месяц, включая ошибки."""
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    today = date.today().isoformat()
    with get_db() as conn:
        return conn.execute(
            """SELECT
                a.id, a.name,
                COUNT(DISTINCT c.id) as company_count,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id
                   AND rd.due_date >= ? AND rd.due_date < ?) as total_deadlines,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id AND rd.status = 'done'
                   AND rd.due_date >= ? AND rd.due_date < ?) as done_deadlines,
                (SELECT COUNT(*) FROM report_deadlines rd
                 JOIN companies cc ON rd.company_id = cc.id
                 WHERE cc.accountant_id = a.id AND rd.status = 'pending'
                   AND rd.due_date >= ? AND rd.due_date < ?
                   AND rd.due_date < ?) as overdue_deadlines,
                (SELECT COUNT(*) FROM accountant_errors ae
                 WHERE ae.accountant_id = a.id
                   AND ae.error_date >= ? AND ae.error_date < ?) as error_count,
                (SELECT COALESCE(SUM(aw.hours),0) FROM additional_works aw
                 WHERE aw.accountant_id = a.id
                   AND aw.work_date >= ? AND aw.work_date < ?) as extra_hours,
                (SELECT COALESCE(SUM(aw.amount),0) FROM additional_works aw
                 WHERE aw.accountant_id = a.id
                   AND aw.work_date >= ? AND aw.work_date < ?) as extra_amount
               FROM accountants a
               LEFT JOIN companies c ON c.accountant_id = a.id AND c.is_active = 1
               GROUP BY a.id, a.name
               ORDER BY a.name""",
            (start, end,       # total_deadlines
             start, end,       # done_deadlines
             start, end, today,  # overdue: в рамках месяца И уже прошедшие
             start, end,       # error_count
             start, end,       # extra_hours
             start, end)       # extra_amount
        ).fetchall()
