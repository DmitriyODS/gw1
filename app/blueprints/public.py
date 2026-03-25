import os
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from extensions import db
from models import Task, TaskStatus, TaskTag, Urgency, Department, TaskAttachment

public_bp = Blueprint('public', __name__)

PLATFORMS = ['Сайт', 'Внешние соц. сети', 'Внутренние соц. сети', 'Афиша']
TASK_TYPES = [
    ('pub_images',           'Картинки для публикаций'),
    ('banner',               'Разработка баннера'),
    ('poster',               'Разработка афиши'),
    ('presentation',         'Разработка презентации'),
    ('presentation_update',  'Доработка презентации'),
    ('text_writing',         'Написание текста'),
    ('handout',              'Разработка раздатки'),
    ('placement',            'Размещение материалов'),
    ('internal',             'Внутренняя работа'),
    ('external',             'Внешняя работа'),
    ('water_plants',         'Полить цветы'),
    ('exports',              'Подготовка выгрузок'),
    ('surveys',              'Создание опросов'),
    ('photo_edit',           'Обработка фото'),
    ('video_edit',           'Монтаж ролика'),
    ('video_shoot',          'Съёмка ролика'),
    ('photo_shoot',          'Фотосъёмка'),
    ('meeting',              'Планёрка'),
    ('mail_work',            'Работа с почтой'),
    ('cloud_work',           'Работа с облаками'),
    ('stand_design',         'Разработка стендов'),
    ('pub_design',           'Разработка дизайна для публикаций'),
    ('branded',              'Разработка брендированной продукции'),
    ('small_design',         'Мелкий дизайн'),
]
EXTERNAL_TASK_TYPES = TASK_TYPES  # все типы видны везде
_INTERNAL_ONLY = set()  # больше нет внутренних типов
PUB_SUBTYPES = [('news', 'Новость'), ('event', 'Мероприятие')]

# Auto-tags suggested/assigned by task type
AUTO_TAGS = {
    'pub_images':           ['дизайн'],
    'banner':               ['дизайн'],
    'poster':               ['дизайн'],
    'presentation':         ['дизайн'],
    'presentation_update':  ['дизайн'],
    'text_writing':         ['текст'],
    'handout':              ['дизайн'],
    'stand_design':         ['дизайн'],
    'pub_design':           ['дизайн'],
    'branded':              ['дизайн'],
    'small_design':         ['дизайн'],
    'photo_edit':           ['фото/видео'],
    'video_edit':           ['фото/видео'],
    'video_shoot':          ['фото/видео'],
    'photo_shoot':          ['фото/видео'],
    'internal':             ['внутреннее'],
    'external':             ['внешнее'],
}


@public_bp.route('/api/departments')
def api_departments():
    """Returns active departments as JSON — used by forms to populate selects dynamically."""
    depts = Department.query.order_by(Department.name).all()
    return jsonify([{'id': d.id, 'name': d.name, 'head': d.head} for d in depts])


@public_bp.route('/api/task-types')
def api_task_types():
    """Returns task type list as JSON — queries DB, falls back to hardcoded list."""
    from models import TaskType
    types = TaskType.query.order_by(TaskType.sort_order, TaskType.label).all()
    if types:
        return jsonify([{'value': t.slug, 'label': t.label} for t in types])
    return jsonify([{'value': v, 'label': l} for v, l in TASK_TYPES])


@public_bp.route('/submit', methods=['GET', 'POST'])
def submit():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        task_type = request.form.get('task_type')
        dynamic = {}
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

        db.session.commit()
        flash('Заявка успешно отправлена! Ожидайте обработки.', 'success')
        return redirect(url_for('public.submit',
            prefill_name=task.customer_name or '',
            prefill_phone=task.customer_phone or '',
            prefill_email=task.customer_email or '',
            prefill_dept=str(task.department_id or ''),
        ))

    prefill = {
        'name':  request.args.get('prefill_name', ''),
        'phone': request.args.get('prefill_phone', ''),
        'email': request.args.get('prefill_email', ''),
        'dept':  request.args.get('prefill_dept', ''),
    }
    return render_template('public/submit.html', departments=departments,
                           task_types=EXTERNAL_TASK_TYPES, pub_subtypes=PUB_SUBTYPES,
                           platforms=PLATFORMS, prefill=prefill)


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
