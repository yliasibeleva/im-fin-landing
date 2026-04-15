"""
Веб-дашборд для руководителя.
Запуск: python web_app.py
Открыть: http://localhost:8000
Логин: admin / пароль из .env (WEB_PASSWORD)
"""
import asyncio
import os
import secrets
from datetime import date

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from typing import Annotated

import database as db

load_dotenv()

WEB_PASSWORD = os.getenv('WEB_PASSWORD', 'admin')
WEB_PORT = int(os.getenv('WEB_PORT', '8000'))

app = FastAPI(title='Империя Финанс — Дашборд')
templates = Jinja2Templates(directory='templates')
security = HTTPBasic()

# Фильтр для форматирования рублей
templates.env.filters['rub'] = lambda v: f"{int(v or 0):,}".replace(',', '\u00a0')


# ─── Авторизация ──────────────────────────────────────────────────────────────

def require_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    ok = secrets.compare_digest(
        credentials.password.encode('utf-8'),
        WEB_PASSWORD.encode('utf-8')
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={'WWW-Authenticate': 'Basic'},
        )


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def fmt_date(iso: str) -> str:
    if not iso:
        return '—'
    try:
        return date.fromisoformat(iso[:10]).strftime('%d.%m.%Y')
    except ValueError:
        return iso


def days_left(iso: str) -> int:
    try:
        return (date.fromisoformat(iso[:10]) - date.today()).days
    except ValueError:
        return 0


# ─── Маршруты ─────────────────────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
async def dashboard(request: Request, _=Depends(require_auth)):
    today = date.today()

    companies_raw  = await asyncio.to_thread(db.get_all_companies)
    upcoming_raw   = await asyncio.to_thread(db.get_upcoming_deadlines, 7)
    overdue_raw    = await asyncio.to_thread(db.get_overdue_deadlines)
    kpi_raw        = await asyncio.to_thread(db.get_accountant_stats_full, today.year, today.month)

    companies = [dict(c) for c in companies_raw]

    upcoming = []
    for dl in upcoming_raw:
        d = dict(dl)
        d['due_fmt']  = fmt_date(d['due_date'])
        d['days_left'] = days_left(d['due_date'])
        upcoming.append(d)

    overdue = []
    for dl in overdue_raw:
        d = dict(dl)
        d['due_fmt']  = fmt_date(d['due_date'])
        d['days_over'] = abs(days_left(d['due_date']))
        overdue.append(d)

    kpi = []
    for s in kpi_raw:
        d = dict(s)
        total = d.get('total_deadlines') or 0
        done  = d.get('done_deadlines') or 0
        d['pct_done'] = round(done / total * 100) if total > 0 else 0
        kpi.append(d)

    return templates.TemplateResponse('dashboard.html', {
        'request':     request,
        'companies':   companies,
        'upcoming':    upcoming,
        'overdue':     overdue,
        'kpi':         kpi,
        'today':       today.strftime('%d.%m.%Y'),
        'month_label': today.strftime('%B %Y'),
        'stats': {
            'companies':  len(companies),
            'upcoming':   len(upcoming),
            'overdue':    len(overdue),
            'accountants': len(kpi),
        },
    })


if __name__ == '__main__':
    print(f'Дашборд: http://localhost:{WEB_PORT}  |  логин: admin / {WEB_PASSWORD}')
    uvicorn.run('web_app:app', host='127.0.0.1', port=WEB_PORT, reload=False)
