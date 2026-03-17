import os
import random
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, Response, send_from_directory)
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
