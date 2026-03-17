import os
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from extensions import db
from models import Task, TaskStatus, TaskTag, Urgency, Department, TaskAttachment

public_bp = Blueprint('public', __name__)

PLATFORMS = ['Сайт', 'Внешние соц. сети', 'Внутренние соц. сети', 'Афиша']
TASK_TYPES = [
    ('publication',          'Публикация'),
    ('picture',              'Разработка картинки'),
    ('handout',              'Разработка раздатки'),
    ('banner',               'Разработка баннера'),
    ('poster',               'Разработка плаката/афиши'),
    ('presentation_verify',  'Верификация презентации'),
    ('presentation',         'Разработка презентации'),
    ('design_verify',        'Верификация дизайна'),
    ('merch',                'Разработка сувенирной продукции'),
    ('postcard',             'Разработка открыток'),
    ('newsletter',           'Выполнение корпоративных рассылок'),
    ('photo_video',          'Фото/видео сопровождение'),
    ('other',                'Другое'),
    # Internal-only (not shown on public form):
    ('mail_check',           'Проверка почты'),
    ('revision',             'Правки по задаче'),
    ('video_edit',           'Монтаж видео'),
    ('photo_edit',           'Обработка фото'),
    ('dept_internal',        'Внутренняя работа отдела'),
    ('dept_external',        'Внешняя работа отдела'),
]

# Types only available in the internal form — hidden from the public submit form
_INTERNAL_ONLY = {'mail_check', 'revision', 'video_edit', 'photo_edit', 'dept_internal', 'dept_external'}
EXTERNAL_TASK_TYPES = [(v, l) for v, l in TASK_TYPES if v not in _INTERNAL_ONLY]
PUB_SUBTYPES = [('news', 'Новость'), ('event', 'Мероприятие')]

# Auto-tags suggested/assigned by task type
AUTO_TAGS = {
    'publication':         ['публикация'],
    'picture':             ['дизайн'],
    'banner':              ['дизайн'],
    'handout':             ['дизайн'],
    'merch':               ['дизайн'],
    'poster':              ['дизайн'],
    'presentation':        ['дизайн'],
    'presentation_verify': ['дизайн'],
    'design_verify':       ['дизайн'],
    'postcard':            ['дизайн', 'текст'],
    'newsletter':          ['текст'],
    'video_edit':          ['фото/видео'],
    'photo_edit':          ['фото/видео'],
    'photo_video':         ['фото/видео'],
    'mail_check':          ['внутреннее'],
    'dept_internal':       ['внутреннее'],
    'dept_external':       ['внешнее'],
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
        event_date = request.form.get('event_date', '').strip()
        if event_date:
            dynamic['event_date'] = event_date

        auto_tags = list(AUTO_TAGS.get(task_type, []))

        task = Task(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            customer_name=request.form.get('customer_name', '').strip() or None,
            customer_phone=request.form.get('customer_phone', '').strip() or None,
            customer_email=request.form.get('customer_email', '').strip() or None,
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
