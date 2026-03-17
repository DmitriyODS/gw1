import calendar
from datetime import date, datetime
from flask import Blueprint, render_template, request
from flask_login import login_required
from models import Task, TaskStatus

media_plan_bp = Blueprint('media_plan', __name__)

PUB_SUBTYPE_LABELS = {'news': 'Новость', 'event': 'Мероприятие'}
PLATFORM_ICONS = {
    'Сайт': 'bi-globe',
    'Внешние соц. сети': 'bi-share',
    'Внутренние соц. сети': 'bi-people',
    'Афиша': 'bi-megaphone',
}


@media_plan_bp.route('/media-plan')
@login_required
def index():
    month_str = request.args.get('month')
    try:
        year, mon = (int(x) for x in month_str.split('-')) if month_str else (None, None)
        current_month = date(year, mon, 1)
    except Exception:
        today = date.today()
        current_month = date(today.year, today.month, 1)

    # Build prev/next month strings
    if current_month.month == 1:
        prev_month = f'{current_month.year - 1}-12'
    else:
        prev_month = f'{current_month.year}-{current_month.month - 1:02d}'
    if current_month.month == 12:
        next_month = f'{current_month.year + 1}-01'
    else:
        next_month = f'{current_month.year}-{current_month.month + 1:02d}'

    # Calendar grid: list of weeks, each week is list of date (or None for padding)
    cal = calendar.monthcalendar(current_month.year, current_month.month)

    # All publication tasks with deadline in this month OR without deadline
    month_start = datetime(current_month.year, current_month.month, 1)
    if current_month.month == 12:
        month_end = datetime(current_month.year + 1, 1, 1)
    else:
        month_end = datetime(current_month.year, current_month.month + 1, 1)

    tasks_in_month = Task.query.filter(
        Task.task_type == 'publication',
        Task.is_archived == False,
        Task.deadline >= month_start,
        Task.deadline < month_end,
    ).all()

    tasks_no_deadline = Task.query.filter(
        Task.task_type == 'publication',
        Task.is_archived == False,
        Task.deadline == None,
    ).all()

    # Group by day
    by_day = {}
    for t in tasks_in_month:
        d = t.deadline.day
        by_day.setdefault(d, []).append(t)

    MONTH_NAMES_RU = [
        '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]

    return render_template('media_plan/index.html',
        current_month=current_month,
        month_label=f'{MONTH_NAMES_RU[current_month.month]} {current_month.year}',
        prev_month=prev_month,
        next_month=next_month,
        cal=cal,
        by_day=by_day,
        tasks_no_deadline=tasks_no_deadline,
        today=date.today(),
        TaskStatus=TaskStatus,
        PUB_SUBTYPE_LABELS=PUB_SUBTYPE_LABELS,
        PLATFORM_ICONS=PLATFORM_ICONS,
    )
