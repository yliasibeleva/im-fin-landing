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
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                name                 TEXT NOT NULL,
                inn                  TEXT,
                tax_system           TEXT NOT NULL,
                org_type             TEXT DEFAULT 'ООО',
                has_employees        INTEGER DEFAULT 0,
                has_military         INTEGER DEFAULT 0,
                has_stats_reporting  INTEGER DEFAULT 0,
                max_group_id         TEXT,
                accountant_id        INTEGER REFERENCES accountants(id),
                work_standard        TEXT,
                description          TEXT,
                notes                TEXT,
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT DEFAULT (datetime('now'))
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
                due_date      TEXT NOT NULL,
                period        TEXT,
                status        TEXT DEFAULT 'pending',
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
                status        TEXT DEFAULT 'pending',
                priority      TEXT DEFAULT 'normal',
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
        _migrate(conn)


def _migrate(conn) -> None:
    """Добавляет новые колонки в существующую БД (безопасно)."""
    migrations = [
        "ALTER TABLE companies ADD COLUMN work_standard TEXT",
        "ALTER TABLE companies ADD COLUMN org_type TEXT DEFAULT 'ООО'",
        "ALTER TABLE companies ADD COLUMN payroll_accountant_id INTEGER REFERENCES accountants(id)",
        "ALTER TABLE companies ADD COLUMN operator_id INTEGER REFERENCES accountants(id)",
        "ALTER TABLE accountants ADD COLUMN phone TEXT",
        "ALTER TABLE accountants ADD COLUMN email TEXT",
        "ALTER TABLE accountants ADD COLUMN position TEXT",
        "ALTER TABLE accountants ADD COLUMN is_remote INTEGER DEFAULT 0",
        "ALTER TABLE accountants ADD COLUMN tg TEXT",
        "ALTER TABLE companies ADD COLUMN description TEXT",
        "ALTER TABLE companies ADD COLUMN has_stats_reporting INTEGER DEFAULT 0",
        "ALTER TABLE companies ADD COLUMN hr_accountant_id INTEGER REFERENCES accountants(id)",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except Exception:
            pass


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
    notes: str = None,
    description: str = None,
    has_stats_reporting: bool = False,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO companies
               (name, inn, tax_system, org_type, has_employees, has_military,
                has_stats_reporting, max_group_id, accountant_id, work_standard,
                notes, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, inn, tax_system, org_type,
             int(has_employees), int(has_military), int(has_stats_reporting),
             max_group_id, accountant_id, work_standard, notes, description)
        )
        return cur.lastrowid


def get_all_companies(active_only: bool = True) -> list:
    with get_db() as conn:
        q = """SELECT c.*,
                      a1.name as accountant_name,
                      a2.name as payroll_accountant_name,
                      a3.name as operator_name,
                      a4.name as hr_accountant_name
               FROM companies c
               LEFT JOIN accountants a1 ON c.accountant_id = a1.id
               LEFT JOIN accountants a2 ON c.payroll_accountant_id = a2.id
               LEFT JOIN accountants a3 ON c.operator_id = a3.id
               LEFT JOIN accountants a4 ON c.hr_accountant_id = a4.id"""
        if active_only:
            q += " WHERE c.is_active = 1"
        q += " ORDER BY c.name"
        return conn.execute(q).fetchall()


def get_company(company_id: int):
    with get_db() as conn:
        return conn.execute(
            """SELECT c.*,
                      a1.name as accountant_name,
                      a2.name as payroll_accountant_name,
                      a3.name as operator_name,
                      a4.name as hr_accountant_name
               FROM companies c
               LEFT JOIN accountants a1 ON c.accountant_id = a1.id
               LEFT JOIN accountants a2 ON c.payroll_accountant_id = a2.id
               LEFT JOIN accountants a3 ON c.operator_id = a3.id
               LEFT JOIN accountants a4 ON c.hr_accountant_id = a4.id
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
    due_date: str,
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


def get_deadlines_7days() -> list:
    """Все дедлайны на ближайшие 7 дней (pending + просроченные)."""
    from datetime import timedelta
    today = date.today().isoformat()
    week = (date.today() + timedelta(days=7)).isoformat()
    with get_db() as conn:
        return conn.execute(
            """SELECT rd.*, c.name as company_name, c.max_group_id,
                      a.name as accountant_name, a.max_user_id as accountant_max_id
               FROM report_deadlines rd
               JOIN companies c ON rd.company_id = c.id
               LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE rd.status = 'pending'
                 AND rd.due_date <= ?
                 AND c.is_active = 1
               ORDER BY rd.due_date""",
            (week,)
        ).fetchall()


def get_all_deadlines_full(year: int = None, month: int = None,
                           accountant_id: int = None, company_id: int = None,
                           status: str = None) -> list:
    """Все дедлайны с фильтрами — для страницы Отчётности."""
    today_year = date.today().year
    y = year or today_year
    with get_db() as conn:
        q = """SELECT rd.*, c.name as company_name, c.tax_system,
                      a.name as accountant_name
               FROM report_deadlines rd
               JOIN companies c ON rd.company_id = c.id
               LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE c.is_active = 1
                 AND substr(rd.due_date, 1, 4) = ?"""
        params: list = [str(y)]
        if month:
            q += " AND substr(rd.due_date, 6, 2) = ?"
            params.append(f'{month:02d}')
        if accountant_id:
            q += " AND c.accountant_id = ?"
            params.append(accountant_id)
        if company_id:
            q += " AND rd.company_id = ?"
            params.append(company_id)
        if status:
            q += " AND rd.status = ?"
            params.append(status)
        q += " ORDER BY rd.due_date, c.name"
        return conn.execute(q, params).fetchall()


def generate_deadlines_for_all(year: int = None) -> int:
    """Генерирует дедлайны для всех активных компаний (если ещё нет за этот год)."""
    from calendar_data import generate_deadlines
    y = year or date.today().year
    with get_db() as conn:
        companies = conn.execute(
            "SELECT id, tax_system, org_type, has_employees, has_military, has_stats_reporting "
            "FROM companies WHERE is_active=1"
        ).fetchall()
        total = 0
        for c in companies:
            exists = conn.execute(
                "SELECT 1 FROM report_deadlines WHERE company_id=? AND substr(due_date,1,4)=?",
                (c['id'], str(y))
            ).fetchone()
            if exists:
                continue
            rows = generate_deadlines(
                c['id'], c['tax_system'], c['org_type'],
                bool(c['has_employees']), bool(c['has_military']),
                bool(c['has_stats_reporting']), year=y
            )
            if rows:
                conn.executemany(
                    """INSERT INTO report_deadlines
                       (company_id, report_name, report_type, due_date, period)
                       VALUES (:company_id, :report_name, :report_type, :due_date, :period)""",
                    rows
                )
                total += len(rows)
        return total


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
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM reminder_logs
               WHERE deadline_id = ? AND days_before = ?
                 AND date(sent_at) = date('now')""",
            (deadline_id, days_before)
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


# ─── Обновление компании ──────────────────────────────────────────────────────

def update_company(company_id: int, **fields) -> None:
    allowed = {
        'name', 'inn', 'tax_system', 'org_type', 'has_employees',
        'has_military', 'has_stats_reporting', 'max_group_id', 'accountant_id',
        'work_standard', 'notes', 'is_active', 'payroll_accountant_id',
        'operator_id', 'hr_accountant_id', 'description'
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


# ─── KPI бухгалтеров ──────────────────────────────────────────────────────────

def get_accountant_stats_full(year: int, month: int) -> list:
    """KPI по каждому бухгалтеру за месяц с корректным подсчётом компаний."""
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month+1:02d}-01" if month < 12 else f"{year+1}-01-01"
    today = date.today().isoformat()
    with get_db() as conn:
        return conn.execute(
            """SELECT
                a.id, a.name,
                (SELECT COUNT(*) FROM companies
                 WHERE accountant_id = a.id AND is_active = 1) as company_count,
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
               ORDER BY a.name""",
            (start, end,
             start, end,
             start, end, today,
             start, end,
             start, end,
             start, end)
        ).fetchall()


# ─── Аналитика ────────────────────────────────────────────────────────────────

def get_analytics_summary() -> dict:
    """
    Возвращает аналитику по компаниям:
    - разбивка по налоговым системам
    - разбивка по типам организаций
    - список компаний с описанием для группировки по видам деятельности
    """
    with get_db() as conn:
        # По системам налогообложения
        by_tax = conn.execute(
            """SELECT tax_system, COUNT(*) as cnt
               FROM companies WHERE is_active = 1
               GROUP BY tax_system ORDER BY cnt DESC"""
        ).fetchall()

        # По типам организаций
        by_org = conn.execute(
            """SELECT org_type, COUNT(*) as cnt
               FROM companies WHERE is_active = 1
               GROUP BY org_type ORDER BY cnt DESC"""
        ).fetchall()

        # Общее количество
        total = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active = 1"
        ).fetchone()[0]

        # С сотрудниками / без
        with_emp = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active = 1 AND has_employees = 1"
        ).fetchone()[0]

        # С воинским учётом
        with_mil = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active = 1 AND has_military = 1"
        ).fetchone()[0]

        # Без закреплённого бухгалтера
        no_accountant = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE is_active = 1 AND accountant_id IS NULL"
        ).fetchone()[0]

        # Компании с описанием (для группировки по видам деятельности)
        companies_with_desc = conn.execute(
            """SELECT name, tax_system, org_type, description, accountant_name
               FROM companies c
               LEFT JOIN accountants a ON c.accountant_id = a.id
               WHERE c.is_active = 1
               ORDER BY c.tax_system, c.name"""
        ).fetchall()

        return {
            'total': total,
            'by_tax': by_tax,
            'by_org': by_org,
            'with_employees': with_emp,
            'with_military': with_mil,
            'no_accountant': no_accountant,
            'companies_with_desc': companies_with_desc,
        }
