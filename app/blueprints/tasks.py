import io
import os
import uuid
import zipfile
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, send_file, current_app)
from flask_login import login_required, current_user
from extensions import db
from models import Task, Department, TaskStatus, TaskTag, Urgency, TimeLog, TaskComment, User
from blueprints.public import _save_attachments, PLATFORMS, TASK_TYPES, PUB_SUBTYPES, AUTO_TAGS

tasks_bp = Blueprint('tasks', __name__)


def sorted_tasks(query):
    tasks = query.filter_by(is_archived=False).all()

    def key(t):
        overdue = 0 if t.is_overdue else 1
        urgency = -Urgency.ORDER.get(t.urgency, 2)
        dl = t.deadline or datetime(9999, 1, 1)
        return (overdue, urgency, dl)

    return sorted(tasks, key=key)


@tasks_bp.route('/tasks')
@login_required
def list_tasks():
    from blueprints.plans import convert_due_plans
    convert_due_plans()
    tasks = sorted_tasks(Task.query)
    my_active_task_ids = {
        log.task_id for log in
        TimeLog.query.filter_by(user_id=current_user.id, ended_at=None).all()
    }
    return render_template('tasks/list.html', tasks=tasks,
                           TaskStatus=TaskStatus, Urgency=Urgency,
                           TaskTag=TaskTag,
                           my_active_task_ids=my_active_task_ids)


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
    return render_template('tasks/detail.html', task=task, logs=logs,
                           active_log=active_log, my_active=my_active,
                           subtasks=subtasks, parent_task=parent_task,
                           users=users,
                           TaskStatus=TaskStatus, Urgency=Urgency, TaskTag=TaskTag)


@tasks_bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        task = _task_from_form(request.form, created_by_id=current_user.id)
        # Publication tag auto-added
        if task.task_type == 'publication':
            tags = list(task.tags or [])
            if TaskTag.PUBLICATION not in tags:
                tags.append(TaskTag.PUBLICATION)
            task.tags = tags
        db.session.add(task)
        db.session.flush()
        _save_attachments(request.files.getlist('attachments'), task.id)

        # For publication tasks create child design + text subtasks
        if task.task_type == 'publication':
            shared = dict(
                created_by_id=current_user.id,
                task_type='publication',
                urgency=task.urgency,
                deadline=task.deadline,
                department_id=task.department_id,
                customer_name=task.customer_name,
                customer_phone=task.customer_phone,
                customer_email=task.customer_email,
                description=task.description,
                parent_task_id=task.id,
                status=TaskStatus.NEW,
                dynamic_fields=task.dynamic_fields or {},
            )
            db.session.add(Task(title=f'[Дизайн] {task.title}', tags=[TaskTag.DESIGN], **shared))
            db.session.add(Task(title=f'[Текст] {task.title}', tags=[TaskTag.TEXT], **shared))

        db.session.commit()
        flash('Задача создана', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id))
    return render_template('tasks/form.html', task=None, departments=departments,
                           Urgency=Urgency, TaskTag=TaskTag, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS)


@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        _task_from_form(request.form, task=task)
        _save_attachments(request.files.getlist('attachments'), task.id)
        db.session.commit()
        flash('Задача обновлена', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    return render_template('tasks/form.html', task=task, departments=departments,
                           Urgency=Urgency, TaskTag=TaskTag, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS)


def _task_from_form(form, task=None, created_by_id=None):
    task_type = form.get('task_type')
    dynamic = {}
    if task_type == 'publication':
        dynamic['subtype'] = form.get('subtype')
        dynamic['platforms'] = form.getlist('platforms')
        pub_date = form.get('pub_date', '').strip()
        if pub_date:
            dynamic['pub_date'] = pub_date
        pub_url = form.get('pub_url', '').strip()
        if pub_url:
            dynamic['pub_url'] = pub_url
    elif task_type == 'revision':
        revision_ref = form.get('revision_ref', '').strip()
        if revision_ref:
            dynamic['revision_ref'] = revision_ref
    else:
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

    db.session.commit()
    return jsonify({'success': True, 'assignee_name': new_assignee.full_name})


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
    f = request.files.get('file')
    if not text and (not f or not f.filename):
        flash('Комментарий не может быть пустым', 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))
    comment = TaskComment(task_id=task_id, user_id=current_user.id, text=text or None)
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower()
        fname = f'{uuid.uuid4().hex}{ext}'
        f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
        comment.filename = fname
        comment.original_name = f.filename
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('tasks.detail', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(task_id, comment_id):
    comment = TaskComment.query.filter_by(id=comment_id, task_id=task_id).first_or_404()
    if comment.user_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    if comment.filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], comment.filename)
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
    """Returns {task_id: {status, assigned_to}} for all active tasks."""
    tasks = (Task.query.filter_by(is_archived=False)
             .with_entities(Task.id, Task.status, Task.assigned_to_id)
             .all())
    return jsonify({
        str(t.id): {'status': t.status, 'assigned_to': t.assigned_to_id}
        for t in tasks
    })


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
