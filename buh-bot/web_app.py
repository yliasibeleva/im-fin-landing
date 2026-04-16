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
from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from typing import Annotated, Optional

import database as db

load_dotenv()

db.init_db()  # применяем миграции при старте

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
    accountants_raw = await asyncio.to_thread(db.get_all_accountants)

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

    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={
            'companies':   companies,
            'upcoming':    upcoming,
            'overdue':     overdue,
            'kpi':         kpi,
            'accountants': [dict(a) for a in accountants_raw],
            'today':       today.strftime('%d.%m.%Y'),
            'month_label': f"{MONTHS_RU[today.month]} {today.year}",
            'stats': {
                'companies':  len(companies),
                'upcoming':   len(upcoming),
                'overdue':    len(overdue),
                'accountants': len(kpi),
            },
        }
    )


MONTHS_RU = ['', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
             'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']


@app.get('/company/{company_id}', response_class=HTMLResponse)
async def company_page(company_id: int, request: Request, _=Depends(require_auth)):
    company_raw = await asyncio.to_thread(db.get_company, company_id)
    if not company_raw:
        raise HTTPException(status_code=404, detail='Компания не найдена')

    company = dict(company_raw)
    today = date.today()
    accountants_raw = await asyncio.to_thread(db.get_all_accountants)

    deadlines_raw = await asyncio.to_thread(db.get_deadlines_for_company, company_id)
    works_raw     = await asyncio.to_thread(db.get_additional_works_for_company_month,
                                            company_id, today.year, today.month)

    deadlines = []
    for dl in deadlines_raw:
        d = dict(dl)
        d['due_fmt']   = fmt_date(d['due_date'])
        d['days_left'] = days_left(d['due_date'])
        deadlines.append(d)

    works = [dict(w) for w in works_raw]
    for w in works:
        w['work_date_fmt'] = fmt_date(w.get('work_date', ''))

    total_hours  = sum(w.get('hours', 0) or 0 for w in works)
    total_amount = sum(w.get('amount', 0) or 0 for w in works)

    pending  = [d for d in deadlines if d['status'] == 'pending']
    done     = [d for d in deadlines if d['status'] == 'done']
    overdue  = [d for d in deadlines if d['status'] == 'overdue']

    return templates.TemplateResponse(
        request=request,
        name='company.html',
        context={
            'company':      company,
            'pending':      pending,
            'done':         done,
            'overdue':      overdue,
            'works':        works,
            'total_hours':  total_hours,
            'total_amount': total_amount,
            'accountants':  [dict(a) for a in accountants_raw],
            'today':        today.strftime('%d.%m.%Y'),
            'today_iso':    today.isoformat(),
            'month_label':  f"{MONTHS_RU[today.month]} {today.year}",
        }
    )


# ─── Редактирование компании ──────────────────────────────────────────────────

@app.post('/companies/add')
async def company_add(
    _=Depends(require_auth),
    name: str = Form(...),
    org_type: str = Form('ООО'),
    tax_system: str = Form('УСН'),
    has_employees: str = Form('0'),
    has_military: str = Form('0'),
    accountant_id: Optional[str] = Form(None),
):
    await asyncio.to_thread(
        db.add_company,
        name=name, inn=None, tax_system=tax_system, org_type=org_type,
        has_employees=int(has_employees == '1'),
        has_military=int(has_military == '1'),
        accountant_id=int(accountant_id) if accountant_id else None,
    )
    return RedirectResponse('/', status_code=303)


@app.post('/company/{company_id}/description')
async def company_description(
    company_id: int,
    _=Depends(require_auth),
    description: str = Form(''),
):
    await asyncio.to_thread(db.update_company, company_id, description=description or None)
    return RedirectResponse(f'/company/{company_id}', status_code=303)


@app.post('/company/{company_id}/delete')
async def company_delete(company_id: int, _=Depends(require_auth)):
    await asyncio.to_thread(db.deactivate_company, company_id)
    return RedirectResponse('/', status_code=303)


@app.post('/company/{company_id}/edit')
async def company_edit(
    company_id: int,
    request: Request,
    _=Depends(require_auth),
    tax_system: str = Form(...),
    org_type: str = Form(...),
    has_employees: str = Form('0'),
    has_military: str = Form('0'),
    accountant_id: Optional[str] = Form(None),
    payroll_accountant_id: Optional[str] = Form(None),
    operator_id: Optional[str] = Form(None),
):
    await asyncio.to_thread(
        db.update_company, company_id,
        tax_system=tax_system,
        org_type=org_type,
        has_employees=int(has_employees == '1'),
        has_military=int(has_military == '1'),
        accountant_id=int(accountant_id) if accountant_id else None,
        payroll_accountant_id=int(payroll_accountant_id) if payroll_accountant_id else None,
        operator_id=int(operator_id) if operator_id else None,
    )
    return RedirectResponse(f'/company/{company_id}', status_code=303)


# ─── Дедлайны ─────────────────────────────────────────────────────────────────

@app.post('/company/{company_id}/deadline/{deadline_id}/done')
async def deadline_done(company_id: int, deadline_id: int, _=Depends(require_auth)):
    await asyncio.to_thread(db.mark_deadline_done, deadline_id)
    return RedirectResponse(f'/company/{company_id}', status_code=303)


@app.post('/company/{company_id}/deadline/add')
async def deadline_add(
    company_id: int,
    _=Depends(require_auth),
    report_name: str = Form(...),
    due_date: str = Form(...),
    period: Optional[str] = Form(None),
):
    await asyncio.to_thread(
        db.add_deadline, company_id, report_name, 'custom', due_date, period or None
    )
    return RedirectResponse(f'/company/{company_id}', status_code=303)


# ─── Доп. работы ──────────────────────────────────────────────────────────────

@app.post('/company/{company_id}/work/add')
async def work_add(
    company_id: int,
    _=Depends(require_auth),
    description: str = Form(...),
    work_type: str = Form('Прочее'),
    work_date: str = Form(...),
    hours: float = Form(0),
    amount: float = Form(0),
    accountant_id: Optional[str] = Form(None),
):
    await asyncio.to_thread(
        db.add_additional_work,
        company_id, description, work_type, work_date,
        int(accountant_id) if accountant_id else None,
        hours, amount,
    )
    return RedirectResponse(f'/company/{company_id}', status_code=303)


# ─── Бухгалтеры ───────────────────────────────────────────────────────────────

@app.get('/accountants', response_class=HTMLResponse)
async def accountants_page(request: Request, _=Depends(require_auth)):
    accs = await asyncio.to_thread(db.get_all_accountants)
    return templates.TemplateResponse(
        request=request, name='accountants.html',
        context={'accountants': [dict(a) for a in accs], 'today': date.today().strftime('%d.%m.%Y')}
    )


@app.post('/accountants/add')
async def accountant_add(
    _=Depends(require_auth),
    name: str = Form(...),
    position: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    tg: Optional[str] = Form(None),
    is_remote: str = Form('0'),
):
    def _add():
        with db.get_db() as conn:
            conn.execute(
                'INSERT INTO accountants (name, position, phone, tg, is_remote) VALUES (?,?,?,?,?)',
                (name, position or None, phone or None, tg or None, int(is_remote))
            )
    await asyncio.to_thread(_add)
    return RedirectResponse('/accountants', status_code=303)


@app.post('/accountants/{accountant_id}/edit')
async def accountant_edit(
    accountant_id: int,
    _=Depends(require_auth),
    name: str = Form(...),
    position: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    tg: Optional[str] = Form(None),
    is_remote: str = Form('0'),
):
    def _update():
        with db.get_db() as conn:
            conn.execute(
                'UPDATE accountants SET name=?, position=?, phone=?, email=?, tg=?, is_remote=? WHERE id=?',
                (name, position or None, phone or None, email or None, tg or None, int(is_remote), accountant_id)
            )
    await asyncio.to_thread(_update)
    return RedirectResponse('/accountants', status_code=303)


@app.post('/accountants/{accountant_id}/delete')
async def accountant_delete(accountant_id: int, _=Depends(require_auth)):
    def _delete():
        with db.get_db() as conn:
            conn.execute('DELETE FROM accountants WHERE id = ?', (accountant_id,))
    await asyncio.to_thread(_delete)
    return RedirectResponse('/accountants', status_code=303)


if __name__ == '__main__':
    print(f'Дашборд: http://localhost:{WEB_PORT}  |  логин: admin / {WEB_PASSWORD}')
    uvicorn.run('web_app:app', host='0.0.0.0', port=WEB_PORT, reload=False)
