import io
import os
import uuid
import zipfile
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, send_file, current_app)
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from extensions import db
from models import Task, Department, TaskStatus, TaskTag, Urgency, TimeLog, TaskComment, CommentAttachment, User
from blueprints.public import _save_attachments, PLATFORMS, TASK_TYPES, PUB_SUBTYPES, AUTO_TAGS

_last_archive_check: datetime = None


def touch(task):
    """Update task.updated_at to now."""
    task.updated_at = datetime.utcnow()


def _maybe_auto_archive():
    global _last_archive_check
    now = datetime.utcnow()
    if _last_archive_check and (now - _last_archive_check).total_seconds() < 3600:
        return
    _last_archive_check = now
    cutoff = now - timedelta(days=7)
    tasks = Task.query.filter(
        Task.status == TaskStatus.DONE,
        Task.completed_at < cutoff,
        Task.completed_at.isnot(None),
        Task.is_archived == False,
    ).all()
    if tasks:
        for t in tasks:
            t.is_archived = True
            t.archived_at = now
        db.session.commit()

tasks_bp = Blueprint('tasks', __name__)


def sorted_tasks(query, sort_new_by_updated=False, include_archived_done=False):
    if include_archived_done:
        tasks = query.filter(
            or_(
                Task.is_archived == False,
                and_(Task.is_archived == True, Task.status == TaskStatus.DONE)
            )
        ).all()
    else:
        tasks = query.filter_by(is_archived=False).all()

    SORT_BY_UPDATED = {TaskStatus.IN_PROGRESS, TaskStatus.PAUSED, TaskStatus.DONE}

    def key(t):
        use_updated = t.status in SORT_BY_UPDATED or (sort_new_by_updated and t.status == TaskStatus.NEW)
        if use_updated:
            # sort by updated_at desc (most recent first) → negate timestamp
            upd = t.updated_at or t.created_at or datetime(2000, 1, 1)
            return (1, 0, datetime(9999, 1, 1) - upd)
        overdue = 0 if t.is_overdue else 1
        urgency = -Urgency.ORDER.get(t.urgency, 2)
        dl = t.deadline or datetime(9999, 1, 1)
        return (overdue, urgency, dl)

    return sorted(tasks, key=key)


@tasks_bp.route('/tasks')
@login_required
def list_tasks():
    _maybe_auto_archive()
    sort_new = request.args.get('sort_new', '0') == '1'
    tasks = sorted_tasks(Task.query, sort_new_by_updated=sort_new, include_archived_done=True)
    my_active_task_ids = {
        log.task_id for log in
        TimeLog.query.filter_by(user_id=current_user.id, ended_at=None).all()
    }
    return render_template('tasks/list.html', tasks=tasks,
                           TaskStatus=TaskStatus, Urgency=Urgency,
                           TaskTag=TaskTag,
                           my_active_task_ids=my_active_task_ids,
                           sort_new=sort_new)


@tasks_bp.route('/tasks/<int:task_id>')
@login_required
def detail(task_id):
    task = Task.query.get_or_404(task_id)
    logs = TimeLog.query.filter_by(task_id=task_id).order_by(TimeLog.started_at.desc()).all()
    active_log = current_user.active_timer
    my_active = TimeLog.query.filter_by(task_id=task_id, user_id=current_user.id, ended_at=None).first()
    subtasks = Task.query.filter_by(parent_task_id=task_id, is_archived=False).all()
    parent_task = Task.query.get(task.parent_task_id) if task.parent_task_id else None
    # Users available for delegation (active, non-TV, excluding current assignee)
    users = (User.query
             .filter_by(is_active=True)
             .filter(User.role != 'tv')
             .order_by(User.full_name)
             .all())
    from blueprints.analytics import TYPE_LABELS
    return render_template('tasks/detail.html', task=task, logs=logs,
                           active_log=active_log, my_active=my_active,
                           subtasks=subtasks, parent_task=parent_task,
                           users=users, type_labels=TYPE_LABELS,
                           TaskStatus=TaskStatus, Urgency=Urgency, TaskTag=TaskTag)


def _create_publication(form, files, created_by_id):
    """Create parent placement task + 2 subtasks (images + text) for publication mode."""
    pub_date = form.get('pub_date_pub', '').strip()
    platforms = form.getlist('pub_platforms')
    deadline_str = form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else None
    urgency = form.get('urgency', Urgency.NORMAL)
    dept_id = form.get('department_id') or None
    title = form.get('title', '').strip()

    dynamic = {}
    if pub_date:
        dynamic['pub_date'] = pub_date
    if platforms:
        dynamic['platforms'] = platforms

    parent = Task(
        created_by_id=created_by_id,
        title=title,
        description=form.get('description', '').strip(),
        customer_name=form.get('customer_name', '').strip() or None,
        customer_phone=form.get('customer_phone', '').strip() or None,
        customer_email=form.get('customer_email', '').strip() or None,
        department_id=dept_id,
        task_type='placement',
        urgency=urgency,
        deadline=deadline,
        dynamic_fields=dynamic,
        tags=['публикация'],
    )
    db.session.add(parent)
    db.session.flush()

    sub_common = dict(
        created_by_id=created_by_id,
        description=form.get('description', '').strip(),
        customer_name=form.get('customer_name', '').strip() or None,
        customer_phone=form.get('customer_phone', '').strip() or None,
        customer_email=form.get('customer_email', '').strip() or None,
        department_id=dept_id,
        urgency=urgency,
        deadline=deadline,
        dynamic_fields=dynamic,
        parent_task_id=parent.id,
    )
    sub1 = Task(title=f'Картинки — {title}', task_type='pub_images', tags=['дизайн'], **sub_common)
    sub2 = Task(title=f'Текст — {title}', task_type='text_writing', tags=['текст'], **sub_common)
    db.session.add(sub1)
    db.session.add(sub2)
    db.session.flush()
    _save_attachments(files, parent.id)
    db.session.commit()
    flash('Создана публикация: родительская задача + 2 подзадачи', 'success')
    return parent.id


@tasks_bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        if request.form.get('create_mode') == 'publication':
            task_id = _create_publication(
                request.form,
                request.files.getlist('attachments'),
                current_user.id,
            )
            return redirect(url_for('tasks.detail', task_id=task_id))
        if not request.form.get('task_type'):
            flash('Выберите тип задачи — это обязательное поле', 'warning')
            return redirect(url_for('tasks.create', **request.args))
        task = _task_from_form(request.form, created_by_id=current_user.id)
        db.session.add(task)
        db.session.flush()
        _save_attachments(request.files.getlist('attachments'), task.id)
        db.session.commit()
        flash('Задача создана', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id, new=1))
    parent_task = None
    parent_id = request.args.get('parent_id')
    if parent_id:
        parent_task = Task.query.get(int(parent_id))
    return render_template('tasks/form.html', task=None, departments=departments,
                           Urgency=Urgency, TaskTag=TaskTag, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS,
                           parent_task=parent_task)


@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        if not request.form.get('task_type'):
            flash('Выберите тип задачи — это обязательное поле', 'warning')
            return redirect(url_for('tasks.edit', task_id=task_id))
        _task_from_form(request.form, task=task)
        _save_attachments(request.files.getlist('attachments'), task.id)
        touch(task)
        db.session.commit()
        flash('Задача обновлена', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    return render_template('tasks/form.html', task=task, departments=departments,
                           Urgency=Urgency, TaskTag=TaskTag, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS)


def _task_from_form(form, task=None, created_by_id=None):
    task_type = form.get('task_type')
    dynamic = {}
    clarification = form.get('clarification', '').strip()
    if clarification:
        dynamic['clarification'] = clarification
    event_date = form.get('event_date', '').strip()
    if event_date:
        dynamic['event_date'] = event_date

    deadline_str = form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else None

    tags = form.getlist('tags')

    if task is None:
        task = Task(created_by_id=created_by_id)

    task.title = form.get('title', '').strip()
    task.description = form.get('description', '').strip()
    task.customer_name = form.get('customer_name', '').strip() or None
    task.customer_phone = form.get('customer_phone', '').strip() or None
    task.customer_email = form.get('customer_email', '').strip() or None
    task.department_id = form.get('department_id') or None
    task.task_type = task_type
    task.urgency = form.get('urgency', Urgency.NORMAL)
    task.deadline = deadline
    task.dynamic_fields = dynamic
    task.tags = tags
    parent_id = form.get('parent_task_id')
    task.parent_task_id = int(parent_id) if parent_id else None
    return task


# ---------- Kanban move ----------

@tasks_bp.route('/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_task(task_id):
    task = Task.query.get_or_404(task_id)
    status = request.json.get('status')
    if status not in TaskStatus.LABELS:
        return jsonify({'error': 'Неверный статус'}), 400
    if status == TaskStatus.IN_PROGRESS:
        return jsonify({'error': 'Нельзя перетащить в «В работе» — используйте кнопку таймера'}), 400
    now = datetime.utcnow()
    for log in task.active_timers:
        log.ended_at = now
    task.status = status
    # Moving back to NEW unassigns the task
    if status == TaskStatus.NEW:
        task.assigned_to_id = None
    touch(task)
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Timer API ----------

@tasks_bp.route('/tasks/<int:task_id>/timer/start', methods=['POST'])
@login_required
def timer_start(task_id):
    task = Task.query.get_or_404(task_id)
    if task.status == TaskStatus.DONE:
        return jsonify({'error': 'Нельзя запустить таймер для завершённой задачи'}), 400

    # Task is claimed by someone else
    if task.assigned_to_id and task.assigned_to_id != current_user.id:
        return jsonify({
            'taken': True,
            'by': task.assigned_to.full_name,
        })

    # Already running on this task for this user
    my_active_here = TimeLog.query.filter_by(
        task_id=task_id, user_id=current_user.id, ended_at=None
    ).first()
    if my_active_here:
        return jsonify({'success': True, 'already_running': True,
                        'started_at': my_active_here.started_at.isoformat()})

    # User has active timer on a different task
    active = current_user.active_timer
    if active and active.task_id != task_id:
        return jsonify({
            'conflict': True,
            'active_task_id': active.task_id,
            'active_task_title': active.task.title,
        })

    log = TimeLog(task_id=task_id, user_id=current_user.id)
    db.session.add(log)
    task.status = TaskStatus.IN_PROGRESS
    task.assigned_to_id = current_user.id   # claim the task
    touch(task)
    db.session.commit()
    return jsonify({'success': True, 'started_at': log.started_at.isoformat()})


@tasks_bp.route('/tasks/<int:task_id>/timer/force_start', methods=['POST'])
@login_required
def timer_force_start(task_id):
    prev_task_status = None
    active = current_user.active_timer
    if active:
        active.ended_at = datetime.utcnow()
        prev_task = active.task
        # Previous task stays assigned to current user (just paused)
        if not prev_task.active_timers:
            prev_task.status = TaskStatus.PAUSED
            prev_task.assigned_to_id = current_user.id
            prev_task_status = TaskStatus.PAUSED
        else:
            prev_task_status = TaskStatus.IN_PROGRESS

    task = Task.query.get_or_404(task_id)
    log = TimeLog(task_id=task_id, user_id=current_user.id)
    task.status = TaskStatus.IN_PROGRESS
    task.assigned_to_id = current_user.id   # claim new task
    touch(task)
    if active:
        touch(active.task)
    db.session.add(log)
    db.session.commit()
    return jsonify({
        'success': True,
        'started_at': log.started_at.isoformat(),
        'prev_task_status': prev_task_status,
    })


@tasks_bp.route('/tasks/<int:task_id>/timer/pause', methods=['POST'])
@login_required
def timer_pause(task_id):
    log = TimeLog.query.filter_by(task_id=task_id, user_id=current_user.id, ended_at=None).first()
    task_status = None
    if log:
        log.ended_at = datetime.utcnow()
        task = Task.query.get(task_id)
        # Task stays assigned to user even when paused
        if not task.active_timers:
            task.status = TaskStatus.PAUSED
            task_status = TaskStatus.PAUSED
        else:
            task_status = TaskStatus.IN_PROGRESS
        touch(task)
        db.session.commit()
    return jsonify({'success': True, 'task_status': task_status})


@tasks_bp.route('/tasks/<int:task_id>/delegate', methods=['POST'])
@login_required
def delegate_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.assigned_to_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав для делегирования'}), 403

    data = request.get_json() or {}
    new_assignee_id = data.get('user_id')
    if not new_assignee_id:
        return jsonify({'error': 'Не указан сотрудник'}), 400

    new_assignee = User.query.get(int(new_assignee_id))
    if not new_assignee or not new_assignee.is_active:
        return jsonify({'error': 'Сотрудник не найден'}), 404

    # Stop current assignee's timer
    if task.assigned_to_id:
        active_log = TimeLog.query.filter_by(
            task_id=task_id, user_id=task.assigned_to_id, ended_at=None
        ).first()
        if active_log:
            active_log.ended_at = datetime.utcnow()

    task.assigned_to_id = int(new_assignee_id)
    if task.status == TaskStatus.IN_PROGRESS:
        task.status = TaskStatus.PAUSED
    touch(task)
    db.session.commit()
    return jsonify({'success': True, 'assignee_name': new_assignee.full_name})


@tasks_bp.route('/tasks/<int:task_id>/admin-pause', methods=['POST'])
@login_required
def admin_pause(task_id):
    """Admin/manager: stop all active timers and pause a task taken by someone else."""
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    task = Task.query.get_or_404(task_id)
    if task.status != TaskStatus.IN_PROGRESS:
        return jsonify({'error': 'Задача не в работе'}), 400
    now = datetime.utcnow()
    for log in task.active_timers:
        log.ended_at = now
    task.status = TaskStatus.PAUSED
    touch(task)
    db.session.commit()
    return jsonify({'ok': True})


@tasks_bp.route('/tasks/<int:task_id>/unassign', methods=['POST'])
@login_required
def unassign_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.assigned_to_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403

    for log in task.active_timers:
        log.ended_at = datetime.utcnow()
    task.assigned_to_id = None
    task.status = TaskStatus.NEW
    touch(task)
    db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/done', methods=['POST'])
@login_required
def mark_done(task_id):
    task = Task.query.get_or_404(task_id)

    if task.open_subtasks_count > 0:
        flash(f'Нельзя закрыть: {task.open_subtasks_count} подзадач ещё не выполнены', 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))

    now = datetime.utcnow()
    for log in task.active_timers:
        log.ended_at = now
    task.status = TaskStatus.DONE
    task.completed_at = now
    task.assigned_to_id = None
    task.updated_at = now
    db.session.commit()
    flash('Задача закрыта', 'success')
    return redirect(url_for('tasks.detail', task_id=task_id))


@tasks_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@tasks_bp.route('/tasks/<int:task_id>/download-zip')
@login_required
def download_zip(task_id):
    from models import TaskAttachment
    task = Task.query.get_or_404(task_id)
    atts = task.attachments.all()
    if not atts:
        flash('Нет файлов для скачивания', 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for att in atts:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
            if os.path.exists(path):
                zf.write(path, att.original_name)
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True, download_name=f'task_{task_id}_files.zip')


@tasks_bp.route('/tasks/<int:task_id>/attachments/<int:att_id>/delete', methods=['POST'])
@login_required
def delete_attachment(task_id, att_id):
    from models import TaskAttachment
    att = TaskAttachment.query.filter_by(id=att_id, task_id=task_id).first_or_404()
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(att)
    db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    task = Task.query.get_or_404(task_id)
    text = request.form.get('text', '').strip()
    files = [f for f in request.files.getlist('files') if f and f.filename]

    if not text and not files:
        flash('Комментарий не может быть пустым', 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))

    # Check total size <= 10 MB
    MAX_SIZE = 10 * 1024 * 1024
    total_size = 0
    for f in files:
        f.seek(0, 2)
        total_size += f.tell()
        f.seek(0)
    if total_size > MAX_SIZE:
        flash('Суммарный размер файлов не должен превышать 10 МБ', 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))

    comment = TaskComment(task_id=task_id, user_id=current_user.id, text=text or None)
    db.session.add(comment)
    db.session.flush()

    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        fname = f'{uuid.uuid4().hex}{ext}'
        f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        att = CommentAttachment(comment_id=comment.id, filename=fname, original_name=f.filename)
        db.session.add(att)

    db.session.commit()
    return redirect(url_for('tasks.detail', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(task_id, comment_id):
    comment = TaskComment.query.filter_by(id=comment_id, task_id=task_id).first_or_404()
    if comment.user_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    # Delete legacy single file
    if comment.filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], comment.filename)
        if os.path.exists(path):
            os.remove(path)
    # Delete new multi-file attachments
    for att in comment.attachments.all():
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/card')
@login_required
def task_card(task_id):
    task = Task.query.get_or_404(task_id)
    my_active_task_ids = {
        log.task_id for log in
        TimeLog.query.filter_by(user_id=current_user.id, ended_at=None).all()
    }
    return render_template('tasks/_card.html', task=task,
                           Urgency=Urgency, TaskStatus=TaskStatus, TaskTag=TaskTag,
                           my_active_task_ids=my_active_task_ids)


@tasks_bp.route('/tasks/my-timer')
@login_required
def my_timer():
    active = current_user.active_timer
    if not active:
        return jsonify({'active': False})
    return jsonify({
        'active': True,
        'task_id': active.task_id,
        'started_at': active.started_at.isoformat(),
    })


@tasks_bp.route('/tasks/poll')
@login_required
def poll_tasks():
    """Returns {task_id: {status, assigned_to, archived}} for active and archived-done tasks."""
    tasks = (Task.query.filter(
        or_(
            Task.is_archived == False,
            and_(Task.is_archived == True, Task.status == TaskStatus.DONE)
        ))
        .with_entities(Task.id, Task.status, Task.assigned_to_id, Task.is_archived)
        .all())
    return jsonify({
        str(t.id): {'status': t.status, 'assigned_to': t.assigned_to_id, 'archived': t.is_archived}
        for t in tasks
    })


@tasks_bp.route('/tasks/<int:task_id>/unarchive', methods=['POST'])
@login_required
def unarchive_task(task_id):
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    task = Task.query.get_or_404(task_id)
    task.is_archived = False
    task.archived_at = None
    db.session.commit()
    return jsonify({'ok': True})


@tasks_bp.route('/tasks/archive-done', methods=['POST'])
@login_required
def archive_done():
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    now = datetime.utcnow()
    tasks = Task.query.filter(
        Task.status == TaskStatus.DONE,
        Task.is_archived == False,
    ).all()
    count = len(tasks)
    for t in tasks:
        t.is_archived = True
        t.archived_at = now
    db.session.commit()
    return jsonify({'ok': True, 'count': count})


@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    if not current_user.can_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.detail', task_id=task_id))
    task = Task.query.get_or_404(task_id)
    for att in task.attachments.all():
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
        if os.path.exists(path):
            os.remove(path)
        db.session.delete(att)
    for log in task.time_logs.all():
        db.session.delete(log)
    # Orphan subtasks: clear their parent reference
    for sub in task.subtasks:
        sub.parent_task_id = None
    # Clear plan references (plans that were converted into this task)
    from models import Plan
    Plan.query.filter_by(converted_task_id=task_id).update({'converted_task_id': None})
    db.session.delete(task)
    db.session.commit()
    flash('Задача удалена', 'success')
    return redirect(url_for('tasks.list_tasks'))
