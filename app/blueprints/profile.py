import os
import random
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, Response, send_from_directory, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import Task, TimeLog, TaskStatus, User

profile_bp = Blueprint('profile', __name__)


# ── Pixel-art identicon generator ────────────────────────────────────────────

def _pixel_art_svg(seed, size=64):
    """Deterministic 8×8 symmetric pixel-art SVG from an integer seed."""
    rng = random.Random(seed)
    hue = rng.randint(0, 359)
    sat = rng.randint(52, 78)
    lit = rng.randint(38, 56)
    bg_lit = 92 if lit < 50 else 10
    fg = f"hsl({hue},{sat}%,{lit}%)"
    bg = f"hsl({hue},{sat // 2}%,{bg_lit}%)"

    # 8 rows × 4 cols, then mirror horizontally → 8×8
    half = [[rng.random() > 0.42 for _ in range(4)] for _ in range(8)]
    grid = [row + list(reversed(row)) for row in half]

    cell = size // 8
    rects = ''.join(
        f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}"/>'
        for r, row in enumerate(grid)
        for c, on in enumerate(row) if on
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f'<rect width="{size}" height="{size}" fill="{bg}"/>'
        f'<g fill="{fg}">{rects}</g>'
        f'</svg>'
    )


# ── Avatar endpoint ───────────────────────────────────────────────────────────

@profile_bp.route('/api/avatar/<int:user_id>')
def avatar(user_id):
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    filename = f'{user_id}.png'
    no_cache = {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache'}
    if os.path.exists(os.path.join(avatars_dir, filename)):
        resp = send_from_directory(avatars_dir, filename, mimetype='image/png')
        resp.headers.update(no_cache)
        return resp
    svg = _pixel_art_svg(user_id)
    return Response(svg, mimetype='image/svg+xml', headers=no_cache)


# ── Profile page ─────────────────────────────────────────────────────────────

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
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def time_secs(start):
        return int(db.session.query(
            func.coalesce(func.sum(
                func.extract('epoch',
                             func.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
            ), 0)
        ).filter(TimeLog.user_id == current_user.id,
                 TimeLog.started_at >= start).scalar() or 0)

    total_time_all = int(db.session.query(
        func.coalesce(func.sum(
            func.extract('epoch',
                         func.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
        ), 0)
    ).filter(TimeLog.user_id == current_user.id).scalar() or 0)

    tasks_created = Task.query.filter_by(created_by_id=current_user.id).count()
    tasks_done = Task.query.filter_by(
        created_by_id=current_user.id, status=TaskStatus.DONE).count()

    subq = db.session.query(
        TimeLog.task_id,
        func.max(TimeLog.started_at).label('last_worked')
    ).filter(TimeLog.user_id == current_user.id
             ).group_by(TimeLog.task_id).subquery()

    recent_logs = db.session.query(Task).join(
        subq, Task.id == subq.c.task_id
    ).order_by(subq.c.last_worked.desc()).limit(5).all()

    has_custom_avatar = os.path.exists(
        os.path.join(current_app.root_path, 'static', 'avatars',
                     f'{current_user.id}.png'))

    return render_template('profile.html',
                           tasks_created=tasks_created,
                           tasks_done=tasks_done,
                           time_week=time_secs(week_start),
                           time_month=time_secs(month_start),
                           time_all=total_time_all,
                           recent_tasks=recent_logs,
                           TaskStatus=TaskStatus,
                           has_custom_avatar=has_custom_avatar)


# ── Profile stats API ─────────────────────────────────────────────────────────

@profile_bp.route('/api/profile/stats')
@login_required
def profile_stats_api():
    from models import Task, TimeLog, TaskStatus
    from blueprints.analytics import TYPE_LABELS
    from collections import defaultdict

    mode = request.args.get('mode', 'day')  # day | week | month
    offset = int(request.args.get('offset', 0))  # 0=current, -1=prev, etc.
    tz_hours = current_app.config.get('TZ_OFFSET_HOURS', 3)

    now_utc = datetime.utcnow()
    now_local = now_utc + timedelta(hours=tz_hours)

    if mode == 'day':
        day = (now_local + timedelta(days=offset)).date()
        start_local = datetime(day.year, day.month, day.day, 0, 0, 0)
        end_local   = datetime(day.year, day.month, day.day, 23, 59, 59)
        label = day.strftime('%d.%m.%Y')
    elif mode == 'week':
        cur_monday = (now_local - timedelta(days=now_local.weekday())).date()
        monday = cur_monday + timedelta(weeks=offset)
        sunday = monday + timedelta(days=6)
        start_local = datetime(monday.year, monday.month, monday.day, 0, 0, 0)
        end_local   = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59)
        label = f'{monday.strftime("%d.%m")} – {sunday.strftime("%d.%m.%Y")}'
    else:  # month
        import calendar
        year = now_local.year
        month = now_local.month + offset
        while month <= 0:
            month += 12; year -= 1
        while month > 12:
            month -= 12; year += 1
        last_day = calendar.monthrange(year, month)[1]
        start_local = datetime(year, month, 1, 0, 0, 0)
        end_local   = datetime(year, month, last_day, 23, 59, 59)
        label = start_local.strftime('%B %Y')

    start_utc = start_local - timedelta(hours=tz_hours)
    end_utc   = end_local   - timedelta(hours=tz_hours)

    # Done tasks the user worked on in period (assigned_to_id is cleared on done)
    worked_task_ids = db.session.query(TimeLog.task_id).filter(
        TimeLog.user_id == current_user.id,
        TimeLog.ended_at.isnot(None),
    ).distinct().subquery()
    done_tasks = Task.query.filter(
        Task.id.in_(worked_task_ids),
        Task.status == TaskStatus.DONE,
        Task.completed_at >= start_utc,
        Task.completed_at <= end_utc,
        Task.completed_at.isnot(None),
    ).all()

    # Time logs in period for current user
    logs = TimeLog.query.filter(
        TimeLog.user_id == current_user.id,
        TimeLog.started_at >= start_utc,
        TimeLog.started_at <= end_utc,
        TimeLog.ended_at.isnot(None),
    ).all()

    # Group time by task_id
    time_by_task = defaultdict(float)
    for log in logs:
        time_by_task[log.task_id] += (log.ended_at - log.started_at).total_seconds()

    # Group by type
    by_type = defaultdict(lambda: {'cnt': 0, 'secs': 0})
    total_secs_from_tasks = 0
    for task in done_tasks:
        type_key = task.task_type or 'other'
        type_label = TYPE_LABELS.get(type_key, type_key)
        by_type[type_label]['cnt'] += 1
        secs = time_by_task.get(task.id, 0)
        by_type[type_label]['secs'] += secs
        total_secs_from_tasks += secs

    # Total time in period (all logs)
    total_period_secs = int(sum(
        (log.ended_at - log.started_at).total_seconds() for log in logs
    ))

    type_list = sorted(
        [{'label': k, 'cnt': v['cnt'], 'secs': int(v['secs'])} for k, v in by_type.items()],
        key=lambda x: x['cnt'], reverse=True
    )

    # Compute ranking score/rank for current user in this period
    from blueprints.analytics import compute_staff_scores
    all_scores = compute_staff_scores(start_utc, end_utc, limit=None)
    user_rank_info = next((s for s in all_scores if s['id'] == current_user.id), None)
    score = user_rank_info['score'] if user_rank_info else None
    rank = next((i + 1 for i, s in enumerate(all_scores) if s['id'] == current_user.id), None)
    total_ranked = len(all_scores)

    return jsonify({
        'label': label,
        'total_tasks': len(done_tasks),
        'total_secs': total_period_secs,
        'by_type': type_list,
        'score': score,
        'rank': rank,
        'total_ranked': total_ranked,
    })


# ── User settings API ─────────────────────────────────────────────────────────

@profile_bp.route('/api/user/settings', methods=['POST'])
@login_required
def save_user_settings():
    mail_user     = request.form.get('mail_user', '').strip() or None
    mail_password = request.form.get('mail_password', '').strip()

    current_user.mail_user = mail_user
    if mail_user is None:
        current_user.mail_password = None
    elif mail_password:
        current_user.mail_password = mail_password
    # mail_user set but password empty → keep existing password

    db.session.commit()
    return jsonify({'success': True, 'has_mail': bool(mail_user)})


@profile_bp.route('/api/user/mail-clear', methods=['POST'])
@login_required
def clear_mail_settings():
    current_user.mail_user     = None
    current_user.mail_password = None
    db.session.commit()
    return jsonify({'success': True})


# ── Avatar upload / reset ─────────────────────────────────────────────────────

@profile_bp.route('/profile/avatar', methods=['POST'])
@login_required
def update_avatar():
    avatars_dir = os.path.join(current_app.root_path, 'static', 'avatars')
    os.makedirs(avatars_dir, exist_ok=True)
    action = request.form.get('action', 'upload')

    if action == 'reset':
        path = os.path.join(avatars_dir, f'{current_user.id}.png')
        if os.path.exists(path):
            os.remove(path)
        flash('Аватарка сброшена до пиксель-арта', 'success')
        return redirect(url_for('profile.profile'))

    file = request.files.get('avatar')
    if not file or not file.filename:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile.profile'))

    try:
        from PIL import Image
        img = Image.open(file.stream).convert('RGB')
        w, h = img.size
        mn = min(w, h)
        left, top = (w - mn) // 2, (h - mn) // 2
        img = img.crop((left, top, left + mn, top + mn))
        img = img.resize((256, 256), Image.LANCZOS)
        img.save(os.path.join(avatars_dir, f'{current_user.id}.png'))
        flash('Фото обновлено', 'success')
    except Exception:
        flash('Ошибка при обработке изображения', 'error')

    return redirect(url_for('profile.profile'))
