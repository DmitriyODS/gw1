from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import Task, TimeLog, TaskStatus, User

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        if full_name:
            current_user.full_name = full_name
        if password:
            current_user.set_password(password)
        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('profile.profile'))

    now = datetime.utcnow()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def time_secs(start):
        return int(db.session.query(
            func.coalesce(func.sum(
                func.extract('epoch', func.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
            ), 0)
        ).filter(TimeLog.user_id == current_user.id, TimeLog.started_at >= start).scalar() or 0)

    total_time_all = int(db.session.query(
        func.coalesce(func.sum(
            func.extract('epoch', func.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
        ), 0)
    ).filter(TimeLog.user_id == current_user.id).scalar() or 0)

    tasks_created = Task.query.filter_by(created_by_id=current_user.id).count()
    tasks_done = Task.query.filter_by(created_by_id=current_user.id, status=TaskStatus.DONE).count()

    # Last 5 tasks the user worked on
    subq = db.session.query(
        TimeLog.task_id,
        func.max(TimeLog.started_at).label('last_worked')
    ).filter(
        TimeLog.user_id == current_user.id
    ).group_by(TimeLog.task_id).subquery()

    recent_logs = db.session.query(Task).join(
        subq, Task.id == subq.c.task_id
    ).order_by(subq.c.last_worked.desc()).limit(5).all()

    return render_template('profile.html',
        tasks_created=tasks_created,
        tasks_done=tasks_done,
        time_week=time_secs(week_start),
        time_month=time_secs(month_start),
        time_all=total_time_all,
        recent_tasks=recent_logs,
        TaskStatus=TaskStatus,
    )
