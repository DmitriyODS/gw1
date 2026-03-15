import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, send_file, request, jsonify
from flask_login import login_required
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
    result = {}
    for p in ['day', 'week', 'month', 'year']:
        s = build_stats(p)
        result[p] = {
            'by_status': s['by_status'],
            'dept_labels': [r[0] for r in s['dept_stats']],
            'dept_values': [r[1] for r in s['dept_stats']],
            'dept_by_status': s['dept_by_status'],
            'type_labels': [TYPE_LABELS.get(r[0], r[0] or 'Другое') for r in s['type_stats']],
            'type_values': [r[1] for r in s['type_stats']],
            'type_by_status': s['type_by_status'],
            'top_customers': [{'name': r[0], 'cnt': r[1]} for r in s['top_customers']],
            'top_dept_incoming': [{'name': r[0], 'cnt': r[1]} for r in s['top_dept_incoming']],
        }

    # All-time employee rating
    all_time = build_stats('year')
    result['employees'] = []
    staff = User.query.filter(User.is_active == True).all()
    for u in staff:
        done = Task.query.filter_by(created_by_id=u.id, status=TaskStatus.DONE).count()
        total_secs = db.session.query(
            func.coalesce(func.sum(
                func.extract('epoch', TimeLog.ended_at - TimeLog.started_at)
            ), 0)
        ).filter(TimeLog.user_id == u.id, TimeLog.ended_at != None).scalar() or 0
        result['employees'].append({
            'name': u.full_name,
            'role': u.role,
            'done': done,
            'hours': round(total_secs / 3600, 1),
        })
    result['employees'].sort(key=lambda x: x['done'], reverse=True)

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
