"""
Машина состояний для многошаговых диалогов.
Хранится в памяти — достаточно для single-process бота.
"""
from typing import Optional, Dict, Any


class StateStorage:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    def set(self, user_id: str, state: str, **data) -> None:
        self._data[str(user_id)] = {'state': state, **data}

    def get_state(self, user_id: str) -> Optional[str]:
        entry = self._data.get(str(user_id))
        return entry['state'] if entry else None

    def get_data(self, user_id: str) -> Dict[str, Any]:
        entry = self._data.get(str(user_id))
        if not entry:
            return {}
        return {k: v for k, v in entry.items() if k != 'state'}

    def update(self, user_id: str, **data) -> None:
        entry = self._data.get(str(user_id), {})
        entry.update(data)
        self._data[str(user_id)] = entry

    def clear(self, user_id: str) -> None:
        self._data.pop(str(user_id), None)


storage = StateStorage()

# ── Состояния: добавление компании ───────────────────────────────────────────
ADD_CO_NAME       = 'add_co_name'
ADD_CO_INN        = 'add_co_inn'
ADD_CO_TAX        = 'add_co_tax'
ADD_CO_ORG        = 'add_co_org'
ADD_CO_EMPLOYEES  = 'add_co_employees'
ADD_CO_MILITARY   = 'add_co_military'
ADD_CO_GROUP      = 'add_co_group'
ADD_CO_ACCOUNTANT = 'add_co_accountant'
ADD_CO_CONFIRM    = 'add_co_confirm'

# ── Состояния: добавление бухгалтера ─────────────────────────────────────────
ADD_ACC_NAME   = 'add_acc_name'
ADD_ACC_MAX_ID = 'add_acc_max_id'

# ── Состояния: доп. работа ───────────────────────────────────────────────────
ADD_WORK_COMPANY = 'add_work_company'
ADD_WORK_TYPE    = 'add_work_type'
ADD_WORK_DESC    = 'add_work_desc'
ADD_WORK_HOURS   = 'add_work_hours'
ADD_WORK_AMOUNT  = 'add_work_amount'
ADD_WORK_DATE    = 'add_work_date'

# ── Состояния: добавление задачи ─────────────────────────────────────────────
ADD_TASK_COMPANY     = 'add_task_company'
ADD_TASK_ACCOUNTANT  = 'add_task_accountant'
ADD_TASK_TITLE       = 'add_task_title'
ADD_TASK_DESC        = 'add_task_desc'
ADD_TASK_DUE         = 'add_task_due'
ADD_TASK_PRIORITY    = 'add_task_priority'

# ── Состояния: добавление произвольного дедлайна ─────────────────────────────
ADD_DL_COMPANY  = 'add_dl_company'
ADD_DL_NAME     = 'add_dl_name'
ADD_DL_TYPE     = 'add_dl_type'
ADD_DL_DATE     = 'add_dl_date'
ADD_DL_PERIOD   = 'add_dl_period'

# ── Состояния: редактирование компании ───────────────────────────────────────
EDIT_CO_SELECT  = 'edit_co_select'
EDIT_CO_FIELD   = 'edit_co_field'
EDIT_CO_VALUE   = 'edit_co_value'

# ── Состояния: фиксация ошибки бухгалтера ────────────────────────────────────
ADD_ERR_ACCOUNTANT = 'add_err_accountant'
ADD_ERR_COMPANY    = 'add_err_company'
ADD_ERR_DESC       = 'add_err_desc'
ADD_ERR_DATE       = 'add_err_date'

# ── Состояния: добавление стандарта работы ───────────────────────────────────
ADD_CO_STANDARD    = 'add_co_standard'
