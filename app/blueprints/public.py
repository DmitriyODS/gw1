import os
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from extensions import db
from models import Task, TaskStatus, TaskTag, Urgency, Department, TaskAttachment

public_bp = Blueprint('public', __name__)

PLATFORMS = ['Сайт', 'Внешние соц. сети', 'Внутренние соц. сети', 'Афиша']
TASK_TYPES = [
    ('publication', 'Публикация'),
    ('handout', 'Разработка раздатки'),
    ('banner', 'Разработка баннера'),
    ('merch', 'Разработка сувенирной продукции'),
    ('poster', 'Разработка плаката/афиши'),
    ('presentation', 'Разработка презентации'),
    ('presentation_update', 'Доработка презентации'),
    ('design_verify', 'Верификация дизайна'),
    ('revision', 'Правки по задаче'),
    ('mail_check', 'Проверка почты'),
    ('newsletter', 'Рассылки'),
    ('postcard', 'Открытки'),
    ('video_edit', 'Монтаж видео'),
    ('photo_edit', 'Обработка фото'),
    ('photo_video', 'Фото/видео сопровождение'),
    ('other', 'Другое'),
]

# Types only available in the internal form — hidden from the public submit form
_INTERNAL_ONLY = {'mail_check', 'video_edit', 'photo_edit', 'photo_video', 'revision'}
EXTERNAL_TASK_TYPES = [(v, l) for v, l in TASK_TYPES if v not in _INTERNAL_ONLY]
PUB_SUBTYPES = [('news', 'Новость'), ('event', 'Мероприятие')]

# Auto-tags suggested/assigned by task type
AUTO_TAGS = {
    'publication':          ['публикация'],
    'banner':               ['дизайн'],
    'handout':              ['дизайн'],
    'merch':                ['дизайн'],
    'poster':               ['дизайн'],
    'presentation':         ['дизайн'],
    'presentation_update':  ['дизайн'],
    'design_verify':        ['дизайн'],
    'postcard':             ['дизайн', 'текст'],
    'newsletter':           ['текст'],
    'video_edit':           ['фото/видео'],
    'photo_edit':           ['фото/видео'],
    'photo_video':          ['фото/видео'],
    'mail_check':           ['внутреннее'],
}


@public_bp.route('/api/departments')
def api_departments():
    """Returns active departments as JSON — used by forms to populate selects dynamically."""
    depts = Department.query.order_by(Department.name).all()
    return jsonify([{'id': d.id, 'name': d.name} for d in depts])


@public_bp.route('/api/task-types')
def api_task_types():
    """Returns task type list as JSON — used by internal form to populate select dynamically."""
    return jsonify([{'value': v, 'label': l} for v, l in TASK_TYPES])


@public_bp.route('/submit', methods=['GET', 'POST'])
def submit():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        task_type = request.form.get('task_type')
        dynamic = {}
        if task_type == 'publication':
            dynamic['subtype'] = request.form.get('subtype')
            dynamic['platforms'] = request.form.getlist('platforms')
        else:
            clarification = request.form.get('clarification', '').strip()
            if clarification:
                dynamic['clarification'] = clarification

        auto_tags = list(AUTO_TAGS.get(task_type, []))

        task = Task(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            customer_name=request.form.get('customer_name', '').strip(),
            customer_phone=request.form.get('customer_phone', '').strip(),
            department_id=request.form.get('department_id') or None,
            task_type=task_type,
            tags=auto_tags,
            dynamic_fields=dynamic,
        )
        db.session.add(task)
        db.session.flush()

        _save_attachments(request.files.getlist('attachments'), task.id)

        # For publication tasks create child design + text subtasks
        if task_type == 'publication':
            db.session.add(Task(
                title=f'[Дизайн] {task.title}',
                task_type='publication',
                tags=[TaskTag.DESIGN],
                urgency=Urgency.NORMAL,
                department_id=task.department_id,
                parent_task_id=task.id,
                status=TaskStatus.NEW,
                dynamic_fields={},
            ))
            db.session.add(Task(
                title=f'[Текст] {task.title}',
                task_type='publication',
                tags=[TaskTag.TEXT],
                urgency=Urgency.NORMAL,
                department_id=task.department_id,
                parent_task_id=task.id,
                status=TaskStatus.NEW,
                dynamic_fields={},
            ))

        db.session.commit()
        flash('Заявка успешно отправлена! Ожидайте обработки.', 'success')
        return redirect(url_for('public.submit'))

    return render_template('public/submit.html', departments=departments,
                           task_types=EXTERNAL_TASK_TYPES, pub_subtypes=PUB_SUBTYPES,
                           platforms=PLATFORMS)


def _save_attachments(files, task_id):
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    upload_dir = current_app.config['UPLOAD_FOLDER']
    for f in files:
        if f and f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if allowed is None or ext in allowed:
                fname = f'{uuid.uuid4().hex}{ext}'
                f.save(os.path.join(upload_dir, fname))
                db.session.add(TaskAttachment(
                    task_id=task_id,
                    filename=fname,
                    original_name=f.filename
                ))
