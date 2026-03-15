import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, send_file, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import Task, TimeLog, User, Department, TaskStatus, Urgency

analytics_bp = Blueprint('analytics', __name__)

TYPE_LABELS = {
    'publication': 'Публикация',
    'handout': 'Разработка раздатки',
    'banner': 'Разработка баннера',
    'merch': 'Разработка сувенирной продукции',
    'poster': 'Разработка плаката/афиши',
    'presentation': 'Разработка презентации',
    'design_verify': 'Верификация дизайна',
    'other': 'Другое',
    None: 'Не указан',
}


def get_range(period):
    now = datetime.utcnow()
    if period == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now - timedelta(days=7)
    return start, now


def build_stats(period):
    start, end = get_range(period)

    by_status = {}
    for s in TaskStatus.LABELS:
        by_status[s] = Task.query.filter(
            Task.created_at >= start, Task.status == s
        ).count()

    dept_stats = db.session.query(Department.name, func.count(Task.id)).join(
        Task, Task.department_id == Department.id
    ).filter(Task.created_at >= start).group_by(Department.name).order_by(func.count(Task.id).desc()).all()

    type_stats = db.session.query(Task.task_type, func.count(Task.id)).filter(
        Task.created_at >= start
    ).group_by(Task.task_type).all()

    # Task types by status breakdown
    type_by_status = {}
    for ttype, _ in type_stats:
        label = TYPE_LABELS.get(ttype, ttype or 'Другое')
        type_by_status[label] = {}
        for s in TaskStatus.LABELS:
            type_by_status[label][s] = Task.query.filter(
                Task.created_at >= start,
                Task.task_type == ttype,
                Task.status == s
            ).count()

    # Department by status breakdown
    dept_by_status = {}
    for dname, _ in dept_stats[:8]:
        dept_by_status[dname] = {}
        for s in TaskStatus.LABELS:
            dept_by_status[dname][s] = db.session.query(func.count(Task.id)).join(
                Department, Task.department_id == Department.id
            ).filter(
                Task.created_at >= start,
                Department.name == dname,
                Task.status == s
            ).scalar() or 0

    # Top requesters by customer_name
    top_customers = db.session.query(
        Task.customer_name, func.count(Task.id).label('cnt')
    ).filter(
        Task.created_at >= start, Task.customer_name != None, Task.customer_name != ''
    ).group_by(Task.customer_name).order_by(func.count(Task.id).desc()).limit(10).all()

    # Top departments by incoming tasks
    top_dept_incoming = db.session.query(
        Department.name, func.count(Task.id).label('cnt')
    ).join(Task, Task.department_id == Department.id).filter(
        Task.created_at >= start
    ).group_by(Department.name).order_by(func.count(Task.id).desc()).limit(10).all()

    top_tasks = db.session.query(User.full_name, func.count(Task.id).label('cnt')).join(
        Task, Task.created_by_id == User.id
    ).filter(Task.status == TaskStatus.DONE, Task.created_at >= start).group_by(
        User.full_name
    ).order_by(func.count(Task.id).desc()).limit(10).all()

    top_time = db.session.query(
        User.full_name,
        func.coalesce(func.sum(
            func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)
        ), 0).label('secs')
    ).join(TimeLog, TimeLog.user_id == User.id).filter(
        TimeLog.started_at >= start, TimeLog.ended_at != None
    ).group_by(User.full_name).order_by(func.sum(
        func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)
    ).desc()).limit(10).all()

    return {
        'by_status': by_status,
        'dept_stats': dept_stats,
        'type_stats': type_stats,
        'type_by_status': type_by_status,
        'dept_by_status': dept_by_status,
        'top_customers': top_customers,
        'top_dept_incoming': top_dept_incoming,
        'top_tasks': top_tasks,
        'top_time': top_time,
    }


@analytics_bp.route('/analytics/time')
@login_required
def time_report():
    now = datetime.utcnow()
    period = request.args.get('period', 'week')
    selected_uid = request.args.get('user_id', type=int)

    # Who can see what
    can_see_all = current_user.can_manage
    all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all() if can_see_all else None
    target_uid = (selected_uid if can_see_all else current_user.id)

    # Period start
    start, _ = get_range(period)

    # All-period totals for summary cards
    ranges = {
        'day':   now.replace(hour=0, minute=0, second=0, microsecond=0),
        'week':  (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0),
        'month': now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        'year':  now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
    }

    def _secs(start_dt, uid=None):
        q = db.session.query(
            func.coalesce(func.sum(
                func.extract('epoch', func.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
            ), 0)
        ).filter(TimeLog.started_at >= start_dt)
        if uid:
            q = q.filter(TimeLog.user_id == uid)
        elif not can_see_all:
            q = q.filter(TimeLog.user_id == current_user.id)
        return int(q.scalar() or 0)

    totals = {p: _secs(r, target_uid) for p, r in ranges.items()}

    # Detailed logs for selected period
    q = db.session.query(TimeLog, Task, User).join(
        Task, TimeLog.task_id == Task.id
    ).join(User, TimeLog.user_id == User.id).filter(TimeLog.started_at >= start)
    if target_uid:
        q = q.filter(TimeLog.user_id == target_uid)
    elif not can_see_all:
        q = q.filter(TimeLog.user_id == current_user.id)
    logs = q.order_by(TimeLog.started_at.desc()).all()

    # Group logs by date then by user
    from collections import defaultdict
    by_date = defaultdict(list)
    for log, task, user in logs:
        date_key = log.started_at.date()
        end = log.ended_at or now
        secs = int((end - log.started_at).total_seconds())
        by_date[date_key].append({
            'task_id': task.id, 'task_title': task.title,
            'user_name': user.full_name,
            'started': log.started_at, 'ended': log.ended_at,
            'secs': secs, 'active': log.ended_at is None,
        })

    # Per-user summary for managers (when no specific user selected)
    user_summary = []
    if can_see_all and not target_uid:
        for u in all_users:
            s = _secs(start, u.id)
            if s > 0:
                user_summary.append({'name': u.full_name, 'id': u.id, 'secs': s})
        user_summary.sort(key=lambda x: x['secs'], reverse=True)

    return render_template('analytics/time.html',
        period=period, target_uid=target_uid,
        all_users=all_users, can_see_all=can_see_all,
        totals=totals, by_date=dict(sorted(by_date.items(), reverse=True)),
        user_summary=user_summary)


@analytics_bp.route('/analytics')
@login_required
def dashboard():
    period = request.args.get('period', 'week')
    stats = build_stats(period)
    return render_template('analytics/dashboard.html', period=period,
                           TaskStatus=TaskStatus, Urgency=Urgency, **stats)


@analytics_bp.route('/analytics/tv')
def tv_mode():
    return render_template('analytics/tv.html')


@analytics_bp.route('/analytics/tv/data')
def tv_data():
    from collections import defaultdict
    result = {}

    for p in ['week', 'month', 'year']:
        s = build_stats(p)
        start, _ = get_range(p)
        now = datetime.utcnow()

        # Total time logged in period
        total_secs = int(db.session.query(
            func.coalesce(func.sum(
                func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)
            ), 0)
        ).filter(TimeLog.started_at >= start, TimeLog.ended_at.isnot(None)).scalar() or 0)

        # Burn-up: cumulative created vs done tasks by day
        days_data = defaultdict(lambda: {'created': 0, 'done': 0})
        for t in Task.query.filter(Task.created_at >= start).all():
            d = t.created_at.date()
            days_data[d]['created'] += 1
            if t.status == TaskStatus.DONE:
                days_data[d]['done'] += 1

        dates, c_series, d_series = [], [], []
        c_c = c_d = 0
        cur = start.date()
        while cur <= now.date():
            c_c += days_data[cur]['created']
            c_d += days_data[cur]['done']
            dates.append(cur.strftime('%d.%m'))
            c_series.append(c_c)
            d_series.append(c_d)
            cur += timedelta(days=1)

        # Top by tasks: users with time logged on done tasks
        top_tasks_q = db.session.query(
            User.full_name, func.count(func.distinct(Task.id)).label('cnt')
        ).join(TimeLog, TimeLog.user_id == User.id).join(
            Task, TimeLog.task_id == Task.id
        ).filter(
            TimeLog.started_at >= start, Task.status == TaskStatus.DONE
        ).group_by(User.full_name).order_by(
            func.count(func.distinct(Task.id)).desc()
        ).limit(5).all()

        # Top by time logged
        top_time_q = db.session.query(
            User.full_name,
            func.coalesce(func.sum(
                func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)
            ), 0).label('secs')
        ).join(TimeLog, TimeLog.user_id == User.id).filter(
            TimeLog.started_at >= start, TimeLog.ended_at.isnot(None)
        ).group_by(User.full_name).order_by(
            func.sum(func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)).desc()
        ).limit(5).all()

        # Focus: longest single uninterrupted session
        focus = db.session.query(
            User.full_name, Task.title,
            func.extract('epoch', TimeLog.ended_at - TimeLog.started_at).label('secs')
        ).join(User, TimeLog.user_id == User.id).join(
            Task, TimeLog.task_id == Task.id
        ).filter(
            TimeLog.started_at >= start, TimeLog.ended_at.isnot(None)
        ).order_by(
            func.extract('epoch', TimeLog.ended_at - TimeLog.started_at).desc()
        ).first()

        result[p] = {
            'by_status': s['by_status'],
            'dept_labels': [r[0] for r in s['dept_stats']],
            'dept_values': [r[1] for r in s['dept_stats']],
            'type_labels': [TYPE_LABELS.get(r[0], r[0] or 'Другое') for r in s['type_stats']],
            'type_values': [r[1] for r in s['type_stats']],
            'total_secs': total_secs,
            'burn_up': {'dates': dates, 'created': c_series, 'done': d_series},
            'top_by_tasks': [{'name': r[0], 'cnt': r[1]} for r in top_tasks_q],
            'top_by_time': [{'name': r[0], 'secs': int(r[1])} for r in top_time_q],
            'focus': {
                'name': focus[0], 'task': focus[1], 'secs': int(focus[2])
            } if focus else None,
        }

    return jsonify(result)


@analytics_bp.route('/analytics/export/excel')
@login_required
def export_excel():
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Задачи'
    headers = ['ID', 'Заголовок', 'Тип', 'Статус', 'Срочность', 'Отдел', 'Заказчик',
               'Телефон', 'Дедлайн', 'Создана', 'Время (мин)']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    tasks = Task.query.order_by(Task.created_at.desc()).all()
    for t in tasks:
        ws.append([
            t.id, t.title,
            TYPE_LABELS.get(t.task_type, t.task_type or ''),
            TaskStatus.LABELS.get(t.status, t.status),
            Urgency.LABELS.get(t.urgency, t.urgency),
            t.department.name if t.department else '',
            t.customer_name or '', t.customer_phone or '',
            t.deadline.strftime('%d.%m.%Y %H:%M') if t.deadline else '',
            t.created_at.strftime('%d.%m.%Y %H:%M'),
            round(t.total_seconds / 60),
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='tasks_export.xlsx')


@analytics_bp.route('/analytics/export/pdf')
@login_required
def export_pdf():
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    data = [['ID', 'Заголовок', 'Тип', 'Статус', 'Срочность', 'Заказчик', 'Дедлайн', 'Мин']]
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    for t in tasks:
        data.append([
            str(t.id), t.title[:50],
            TYPE_LABELS.get(t.task_type, t.task_type or '')[:20],
            TaskStatus.LABELS.get(t.status, t.status),
            Urgency.LABELS.get(t.urgency, t.urgency),
            t.customer_name or '',
            t.deadline.strftime('%d.%m.%Y') if t.deadline else '',
            str(round(t.total_seconds / 60)),
        ])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    doc.build([table])
    output.seek(0)
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name='tasks_export.pdf')
