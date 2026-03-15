import io
import os
import zipfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Task, Department, TaskStatus, Urgency, TimeLog
from blueprints.public import _save_attachments, PLATFORMS, TASK_TYPES, PUB_SUBTYPES

tasks_bp = Blueprint('tasks', __name__)


def sorted_tasks(query):
    now = datetime.utcnow()
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
    tasks = sorted_tasks(Task.query)
    return render_template('tasks/list.html', tasks=tasks,
                           TaskStatus=TaskStatus, Urgency=Urgency)


@tasks_bp.route('/tasks/<int:task_id>')
@login_required
def detail(task_id):
    task = Task.query.get_or_404(task_id)
    logs = TimeLog.query.filter_by(task_id=task_id).order_by(TimeLog.started_at.desc()).all()
    active_log = current_user.active_timer
    my_active = TimeLog.query.filter_by(task_id=task_id, user_id=current_user.id, ended_at=None).first()
    return render_template('tasks/detail.html', task=task, logs=logs,
                           active_log=active_log, my_active=my_active,
                           TaskStatus=TaskStatus, Urgency=Urgency)


@tasks_bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.can_admin:
        flash('Недостаточно прав для создания задач', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        task = _task_from_form(request.form, created_by_id=current_user.id)
        db.session.add(task)
        db.session.flush()
        _save_attachments(request.files.getlist('attachments'), task.id)
        db.session.commit()
        flash('Задача создана', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id))
    return render_template('tasks/form.html', task=None, departments=departments,
                           Urgency=Urgency, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS)


@tasks_bp.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    if not current_user.can_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.detail', task_id=task_id))
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        updated = _task_from_form(request.form, task=task)
        _save_attachments(request.files.getlist('attachments'), task.id)
        db.session.commit()
        flash('Задача обновлена', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    return render_template('tasks/form.html', task=task, departments=departments,
                           Urgency=Urgency, task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES, platforms=PLATFORMS)


def _task_from_form(form, task=None, created_by_id=None):
    task_type = form.get('task_type')
    dynamic = {}
    if task_type == 'publication':
        dynamic['subtype'] = form.get('subtype')
        dynamic['platforms'] = form.getlist('platforms')
    else:
        clarification = form.get('clarification', '').strip()
        if clarification:
            dynamic['clarification'] = clarification

    deadline_str = form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M') if deadline_str else None

    if task is None:
        task = Task(created_by_id=created_by_id)

    task.title = form.get('title', '').strip()
    task.description = form.get('description', '').strip()
    task.customer_name = form.get('customer_name', '').strip()
    task.customer_phone = form.get('customer_phone', '').strip()
    task.department_id = form.get('department_id') or None
    task.task_type = task_type
    task.urgency = form.get('urgency', Urgency.NORMAL)
    task.deadline = deadline
    task.dynamic_fields = dynamic
    return task


# ---------- Kanban move ----------

@tasks_bp.route('/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_task(task_id):
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    task = Task.query.get_or_404(task_id)
    status = request.json.get('status')
    if status not in TaskStatus.LABELS:
        return jsonify({'error': 'Неверный статус'}), 400
    if status == TaskStatus.IN_PROGRESS:
        return jsonify({'error': 'Нельзя перетащить в «В работе» — используйте кнопку таймера'}), 400
    # Stop active timers when moving away from in_progress
    if task.status == TaskStatus.IN_PROGRESS:
        for log in task.active_timers:
            log.ended_at = datetime.utcnow()
    task.status = status
    db.session.commit()
    return jsonify({'ok': True})


# ---------- Timer API ----------

@tasks_bp.route('/tasks/<int:task_id>/timer/start', methods=['POST'])
@login_required
def timer_start(task_id):
    task = Task.query.get_or_404(task_id)
    if task.status not in (TaskStatus.NEW, TaskStatus.PAUSED):
        return jsonify({'error': 'Нельзя запустить таймер в текущем статусе'}), 400

    active = current_user.active_timer
    if active and active.task_id != task_id:
        return jsonify({
            'conflict': True,
            'active_task_id': active.task_id,
            'active_task_title': active.task.title
        })

    if not active:
        log = TimeLog(task_id=task_id, user_id=current_user.id)
        db.session.add(log)
        task.status = TaskStatus.IN_PROGRESS
        db.session.commit()
        return jsonify({'success': True, 'started_at': log.started_at.isoformat()})

    return jsonify({'success': True, 'already_running': True,
                    'started_at': active.started_at.isoformat()})


@tasks_bp.route('/tasks/<int:task_id>/timer/force_start', methods=['POST'])
@login_required
def timer_force_start(task_id):
    active = current_user.active_timer
    if active:
        active.ended_at = datetime.utcnow()
        active.task.status = TaskStatus.PAUSED

    task = Task.query.get_or_404(task_id)
    log = TimeLog(task_id=task_id, user_id=current_user.id)
    task.status = TaskStatus.IN_PROGRESS
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True, 'started_at': log.started_at.isoformat()})


@tasks_bp.route('/tasks/<int:task_id>/timer/pause', methods=['POST'])
@login_required
def timer_pause(task_id):
    log = TimeLog.query.filter_by(task_id=task_id, user_id=current_user.id, ended_at=None).first()
    if log:
        log.ended_at = datetime.utcnow()
        task = Task.query.get(task_id)
        # Only pause if no other active timers on this task
        if not task.active_timers:
            task.status = TaskStatus.PAUSED
        db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/review', methods=['POST'])
@login_required
def send_to_review(task_id):
    task = Task.query.get_or_404(task_id)
    log = TimeLog.query.filter_by(task_id=task_id, user_id=current_user.id, ended_at=None).first()
    if log:
        log.ended_at = datetime.utcnow()
    task.status = TaskStatus.REVIEW
    db.session.commit()
    flash('Задача отправлена на проверку', 'success')
    return redirect(url_for('tasks.detail', task_id=task_id))


@tasks_bp.route('/tasks/<int:task_id>/done', methods=['POST'])
@login_required
def mark_done(task_id):
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.detail', task_id=task_id))
    task = Task.query.get_or_404(task_id)
    task.status = TaskStatus.DONE
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
