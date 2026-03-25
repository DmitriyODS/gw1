from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Rhythm, RhythmFrequency, Task, TaskStatus, TaskTag, Urgency, Department
from blueprints.public import TASK_TYPES

rhythms_bp = Blueprint('rhythms', __name__)


@rhythms_bp.route('/rhythms')
@login_required
def index():
    rhythms = Rhythm.query.order_by(Rhythm.name).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('rhythms/index.html',
                           rhythms=rhythms,
                           departments=departments,
                           RhythmFrequency=RhythmFrequency,
                           TaskTag=TaskTag,
                           Urgency=Urgency,
                           task_types=TASK_TYPES)


@rhythms_bp.route('/rhythms/create', methods=['POST'])
@login_required
def create():
    if not request.form.get('task_type'):
        flash('Укажите тип задачи', 'danger')
        return redirect(url_for('rhythms.index'))
    r = _rhythm_from_form(request.form, created_by_id=current_user.id)
    db.session.add(r)
    db.session.commit()
    flash('Ритм создан', 'success')
    return redirect(url_for('rhythms.index'))


@rhythms_bp.route('/rhythms/<int:rhythm_id>/edit', methods=['POST'])
@login_required
def edit(rhythm_id):
    if not request.form.get('task_type'):
        flash('Укажите тип задачи', 'danger')
        return redirect(url_for('rhythms.index'))
    r = Rhythm.query.get_or_404(rhythm_id)
    _rhythm_from_form(request.form, rhythm=r)
    db.session.commit()
    flash('Ритм обновлён', 'success')
    return redirect(url_for('rhythms.index'))


@rhythms_bp.route('/rhythms/<int:rhythm_id>/toggle', methods=['POST'])
@login_required
def toggle(rhythm_id):
    r = Rhythm.query.get_or_404(rhythm_id)
    r.is_active = not r.is_active
    db.session.commit()
    return redirect(url_for('rhythms.index'))


@rhythms_bp.route('/rhythms/<int:rhythm_id>/run', methods=['POST'])
@login_required
def run(rhythm_id):
    r = Rhythm.query.get_or_404(rhythm_id)
    task = _create_task_from_rhythm(r)
    db.session.commit()
    flash(f'Задача «{task.title}» создана из ритма', 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))


@rhythms_bp.route('/rhythms/<int:rhythm_id>/delete', methods=['POST'])
@login_required
def delete(rhythm_id):
    r = Rhythm.query.get_or_404(rhythm_id)
    db.session.delete(r)
    db.session.commit()
    flash('Ритм удалён', 'success')
    return redirect(url_for('rhythms.index'))


def _rhythm_from_form(form, rhythm=None, created_by_id=None):
    if rhythm is None:
        rhythm = Rhythm(created_by_id=created_by_id)

    rhythm.name = form.get('name', '').strip()
    rhythm.description = form.get('description', '').strip() or None
    rhythm.frequency = form.get('frequency', RhythmFrequency.DAILY)
    rhythm.day_of_week = int(form.get('day_of_week', 0)) if form.get('day_of_week') else None
    rhythm.day_of_month = int(form.get('day_of_month', 1)) if form.get('day_of_month') else None
    rhythm.task_title = form.get('task_title', '').strip()
    rhythm.task_description = form.get('task_description', '').strip() or None
    rhythm.task_tags = form.getlist('task_tags')
    rhythm.task_urgency = form.get('task_urgency', Urgency.NORMAL)
    rhythm.task_type = form.get('task_type') or None
    rhythm.department_id = form.get('department_id') or None
    rhythm.trigger_time = form.get('trigger_time', '').strip() or None
    rhythm.is_active = form.get('is_active') == '1'
    return rhythm


def _create_task_from_rhythm(rhythm):
    """Create a Task (and sub-tasks if publication) from the rhythm template."""
    tags = list(rhythm.task_tags or [])

    task = Task(
        title=rhythm.task_title,
        description=rhythm.task_description,
        task_type=rhythm.task_type,
        tags=tags,
        urgency=rhythm.task_urgency or Urgency.NORMAL,
        department_id=rhythm.department_id,
        status=TaskStatus.NEW,
        created_by_id=rhythm.created_by_id,
        dynamic_fields={},
    )

    if rhythm.task_type == 'publication':
        if TaskTag.PUBLICATION not in tags:
            task.tags = tags + [TaskTag.PUBLICATION]

    db.session.add(task)
    db.session.flush()

    if rhythm.task_type == 'publication':
        design_task = Task(
            title=f'[Дизайн] {task.title}',
            created_by_id=rhythm.created_by_id,
            task_type='publication',
            tags=[TaskTag.DESIGN],
            urgency=task.urgency,
            department_id=task.department_id,
            parent_task_id=task.id,
            status=TaskStatus.NEW,
            dynamic_fields={},
        )
        text_task = Task(
            title=f'[Текст] {task.title}',
            created_by_id=rhythm.created_by_id,
            task_type='publication',
            tags=[TaskTag.TEXT],
            urgency=task.urgency,
            department_id=task.department_id,
            parent_task_id=task.id,
            status=TaskStatus.NEW,
            dynamic_fields={},
        )
        db.session.add(design_task)
        db.session.add(text_task)

    rhythm.last_run_at = datetime.utcnow()
    return task
