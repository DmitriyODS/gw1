import os
import uuid
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from extensions import db
from models import Task, Department, TaskAttachment

public_bp = Blueprint('public', __name__)

PLATFORMS = ['Сайт', 'Внешние соц. сети', 'Внутренние соц. сети', 'Афиша']
TASK_TYPES = [
    ('publication', 'Публикация'),
    ('handout', 'Разработка раздатки'),
    ('banner', 'Разработка баннера'),
    ('merch', 'Разработка сувенирной продукции'),
    ('poster', 'Разработка плаката/афиши'),
    ('presentation', 'Разработка презентации'),
    ('design_verify', 'Верификация дизайна'),
    ('other', 'Другое'),
]
PUB_SUBTYPES = [('news', 'Новость'), ('event', 'Мероприятие')]


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

        task = Task(
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            customer_name=request.form.get('customer_name', '').strip(),
            customer_phone=request.form.get('customer_phone', '').strip(),
            department_id=request.form.get('department_id') or None,
            task_type=task_type,
            dynamic_fields=dynamic,
        )
        db.session.add(task)
        db.session.flush()

        _save_attachments(request.files.getlist('attachments'), task.id)
        db.session.commit()
        flash('Заявка успешно отправлена! Ожидайте обработки.', 'success')
        return redirect(url_for('public.submit'))

    return render_template('public/submit.html', departments=departments,
                           task_types=TASK_TYPES, pub_subtypes=PUB_SUBTYPES,
                           platforms=PLATFORMS)


def _save_attachments(files, task_id):
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    upload_dir = current_app.config['UPLOAD_FOLDER']
    for f in files:
        if f and f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext in allowed:
                fname = f'{uuid.uuid4().hex}{ext}'
                f.save(os.path.join(upload_dir, fname))
                db.session.add(TaskAttachment(
                    task_id=task_id,
                    filename=fname,
                    original_name=f.filename
                ))
