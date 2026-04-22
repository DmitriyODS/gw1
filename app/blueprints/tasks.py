import io
import os
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, send_file, current_app)
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from extensions import db
from models import Task, Department, TaskStatus, TaskTag, Urgency, TimeLog, TaskComment, CommentAttachment, User, GameScore
from blueprints.public import _save_attachments, PLATFORMS, TASK_TYPES, PUB_SUBTYPES, AUTO_TAGS

_last_archive_check: datetime = None

# ── Фоновая загрузка на Яндекс Диск ──────────────────────────────────────────
_ydisk_jobs: dict = {}
_jobs_lock = threading.Lock()


def _bg_upload_to_ydisk(app, job_id, comment_id, temp_files, ydisk_token, task_id, task_title, user_full_name, tz_offset):
    """
    Фоновый поток: загружает файлы из temp-директории на YDisk,
    создаёт CommentAttachment-записи, удаляет temp-файлы.
    temp_files: список (temp_path, original_name)
    """
    import shutil as _sh

    def _set(key, val):
        with _jobs_lock:
            _ydisk_jobs[job_id][key] = val

    def _inc_done():
        with _jobs_lock:
            _ydisk_jobs[job_id]['done'] += 1

    tmp_dir = None
    if temp_files:
        tmp_dir = os.path.dirname(temp_files[0][0])

    with app.app_context():
        try:
            _set('status', 'uploading')
            from services.yandex_disk import (
                _ensure_folder, _sanitize, _publish_file, ROOT_FOLDER,
            )
            import urllib.request
            import json as _json

            # Строим структуру папок (один раз)
            from datetime import timedelta as _td
            now_local = datetime.utcnow() + _td(hours=tz_offset)
            date_str = now_local.strftime('%Y.%m.%d')
            time_str = now_local.strftime('%H-%M-%S')
            task_folder = _sanitize(task_title)
            user_folder = _sanitize(user_full_name)
            comment_path = f'{ROOT_FOLDER}/{date_str}/{task_folder}/{user_folder}/{time_str}'

            for segment in [
                ROOT_FOLDER,
                f'{ROOT_FOLDER}/{date_str}',
                f'{ROOT_FOLDER}/{date_str}/{task_folder}',
                f'{ROOT_FOLDER}/{date_str}/{task_folder}/{user_folder}',
                comment_path,
            ]:
                _ensure_folder(ydisk_token, segment)

            import urllib.parse
            import urllib.error as _ue
            disk_api = 'https://cloud-api.yandex.net/v1/disk'

            def _upload_file_unique(token, folder_path, sanitized_name, data):
                """
                Загрузить данные в folder_path/sanitized_name с overwrite=false.
                При конфликте (409) пробует folder_path/base_N.ext пока не найдёт свободное имя.
                Возвращает итоговый remote_path.
                """
                if '.' in sanitized_name:
                    base, ext = sanitized_name.rsplit('.', 1)
                else:
                    base, ext = sanitized_name, ''

                index = 0
                while True:
                    if index == 0:
                        candidate = sanitized_name
                    else:
                        candidate = f'{base}_{index}.{ext}' if ext else f'{base}_{index}'
                    remote_path = f'{folder_path}/{candidate}'
                    params = urllib.parse.urlencode({'path': remote_path, 'overwrite': 'false'})
                    req = urllib.request.Request(f'{disk_api}/resources/upload?{params}')
                    req.add_header('Authorization', f'OAuth {token}')
                    req.add_header('Accept', 'application/json')
                    try:
                        with urllib.request.urlopen(req) as resp:
                            upload_url = _json.loads(resp.read().decode())['href']
                    except _ue.HTTPError as e:
                        if e.code == 409:
                            index += 1
                            continue
                        raise
                    put_req = urllib.request.Request(upload_url, data=data, method='PUT')
                    put_req.add_header('Content-Type', 'application/octet-stream')
                    with urllib.request.urlopen(put_req):
                        pass
                    return remote_path

            file_results = []
            for temp_path, original_name in temp_files:
                with _jobs_lock:
                    _ydisk_jobs[job_id]['current_file'] = original_name

                with open(temp_path, 'rb') as fh:
                    data = fh.read()

                remote_path = _upload_file_unique(
                    ydisk_token, comment_path, _sanitize(original_name), data
                )

                file_url = _publish_file(ydisk_token, remote_path)
                file_results.append({
                    'original_name': original_name,
                    'yadisk_url': file_url,
                    'yadisk_path': remote_path,
                })
                _inc_done()
                with _jobs_lock:
                    _ydisk_jobs[job_id]['current_file'] = ''

            folder_url = _publish_file(ydisk_token, comment_path)

            # Сохраняем в БД
            for res in file_results:
                att = CommentAttachment(
                    comment_id=comment_id,
                    original_name=res['original_name'],
                    yadisk_url=res['yadisk_url'],
                    yadisk_path=res['yadisk_path'],
                    yadisk_folder_url=folder_url,
                )
                db.session.add(att)
            db.session.commit()

            _set('status', 'complete')

        except Exception as e:
            app.logger.error(f'YDisk bg upload failed: {e}')
            # Fallback: попробовать сохранить локально
            fallback_ok = False
            try:
                db.session.rollback()
                upload_folder = app.config['UPLOAD_FOLDER']
                for temp_path, original_name in temp_files:
                    ext = os.path.splitext(original_name)[1].lower()
                    fname = f'{uuid.uuid4().hex}{ext}'
                    dst = os.path.join(upload_folder, fname)
                    _sh.copy2(temp_path, dst)
                    db.session.add(CommentAttachment(
                        comment_id=comment_id,
                        filename=fname,
                        original_name=original_name,
                    ))
                db.session.commit()
                fallback_ok = True
            except Exception as e2:
                app.logger.error(f'YDisk fallback local save failed: {e2}')

            if fallback_ok:
                # Файлы сохранены локально — транзакция считается успешной
                _set('status', 'complete')
            else:
                # Ни YDisk, ни локальное хранилище не сработали — откатываем комментарий
                try:
                    db.session.rollback()
                    from models import TaskComment as _TC
                    comment_obj = _TC.query.get(comment_id)
                    if comment_obj:
                        db.session.delete(comment_obj)
                        db.session.commit()
                except Exception as e3:
                    app.logger.error(f'Comment rollback failed: {e3}')
                _set('status', 'error')
                _set('error', str(e))
        finally:
            # Удаляем temp-директорию
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    _sh.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass


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
    updated = Task.query.filter(
        Task.status == TaskStatus.DONE,
        Task.completed_at < cutoff,
        Task.completed_at.isnot(None),
        Task.is_archived == False,
    ).update({'is_archived': True, 'archived_at': now}, synchronize_session=False)
    if updated:
        db.session.commit()

tasks_bp = Blueprint('tasks', __name__)

DONE_PAGE_SIZE = 20


def sorted_tasks(query, sort_new_by_updated=False, include_archived_done=False):
    query = query.options(joinedload(Task.assigned_to), joinedload(Task.department))
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


def _build_secs(task_ids):
    """Aggregate time-logged seconds for given task IDs (single SQL query)."""
    if not task_ids:
        return {}
    from sqlalchemy import func as sqlfunc
    now = datetime.utcnow()
    rows = db.session.query(
        TimeLog.task_id,
        sqlfunc.coalesce(sqlfunc.sum(
            sqlfunc.extract('epoch', sqlfunc.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
        ), 0).label('secs')
    ).filter(TimeLog.task_id.in_(task_ids)).group_by(TimeLog.task_id).all()
    return {r.task_id: int(r.secs) for r in rows}


@tasks_bp.route('/tasks')
@login_required
def list_tasks():
    _maybe_auto_archive()
    sort_new = request.args.get('sort_new', '0') == '1'

    # --- Не-done задачи: все, Python-сортировка (обычно мало) ---
    non_done_tasks = sorted_tasks(
        Task.query.filter(Task.status != TaskStatus.DONE),
        sort_new_by_updated=sort_new,
        include_archived_done=False,
    )

    # --- Done: первая страница из БД, включая архивные (для JS-тоггла) ---
    done_q = (
        Task.query
        .options(joinedload(Task.assigned_to), joinedload(Task.department))
        .filter(Task.status == TaskStatus.DONE)
        .order_by(Task.updated_at.desc(), Task.id.desc())
    )
    done_total = done_q.count()
    done_tasks = done_q.limit(DONE_PAGE_SIZE).all()
    done_has_more = done_total > DONE_PAGE_SIZE

    tasks = non_done_tasks + done_tasks

    # 1 запрос: активные таймеры
    from collections import defaultdict
    all_active_logs = TimeLog.query.options(joinedload(TimeLog.user)).filter_by(ended_at=None).all()
    active_timers_by_task = defaultdict(list)
    for log in all_active_logs:
        active_timers_by_task[log.task_id].append(log)
    my_active_task_ids = {log.task_id for log in all_active_logs if log.user_id == current_user.id}

    # 1 запрос: секунды только для загруженных задач
    secs_by_task = _build_secs([t.id for t in tasks])

    # Просроченные задачи для модалки
    now = datetime.utcnow()
    overdue_tasks = Task.query.filter(
        Task.status != TaskStatus.DONE,
        Task.is_archived == False,
        Task.deadline < now,
        Task.deadline.isnot(None),
    ).order_by(Task.deadline.asc()).limit(50).all()

    return render_template('tasks/list.html', tasks=tasks,
                           TaskStatus=TaskStatus, Urgency=Urgency,
                           TaskTag=TaskTag,
                           my_active_task_ids=my_active_task_ids,
                           active_timers_by_task=active_timers_by_task,
                           secs_by_task=secs_by_task,
                           sort_new=sort_new,
                           done_total=done_total,
                           done_has_more=done_has_more,
                           done_page_size=DONE_PAGE_SIZE,
                           overdue_tasks=overdue_tasks)


@tasks_bp.route('/tasks/done-more')
@login_required
def done_more():
    """AJAX: следующая страница Done-колонки → HTML-фрагмент с карточками."""
    offset = max(0, request.args.get('offset', 0, int))
    tasks = (
        Task.query
        .options(joinedload(Task.assigned_to), joinedload(Task.department))
        .filter(Task.status == TaskStatus.DONE)
        .order_by(Task.updated_at.desc(), Task.id.desc())
        .offset(offset)
        .limit(DONE_PAGE_SIZE + 1)  # +1 чтобы понять, есть ли ещё
        .all()
    )
    has_more = len(tasks) > DONE_PAGE_SIZE
    tasks = tasks[:DONE_PAGE_SIZE]

    if not tasks:
        return '', 204

    from collections import defaultdict
    task_ids = [t.id for t in tasks]
    secs_by_task = _build_secs(task_ids)
    active_logs = (
        TimeLog.query
        .options(joinedload(TimeLog.user))
        .filter(TimeLog.task_id.in_(task_ids), TimeLog.ended_at.is_(None))
        .all()
    )
    active_timers_by_task = defaultdict(list)
    for log in active_logs:
        active_timers_by_task[log.task_id].append(log)
    my_active_task_ids = {log.task_id for log in active_logs if log.user_id == current_user.id}

    return render_template(
        'tasks/_done_cards.html',
        tasks=tasks,
        has_more=has_more,
        next_offset=offset + DONE_PAGE_SIZE,
        secs_by_task=secs_by_task,
        active_timers_by_task=active_timers_by_task,
        my_active_task_ids=my_active_task_ids,
        TaskStatus=TaskStatus, Urgency=Urgency, TaskTag=TaskTag,
    )


@tasks_bp.route('/tasks/search')
@login_required
def search_tasks():
    """AJAX: полнотекстовый поиск по заголовку → HTML-фрагмент колонок для JS-подстановки."""
    q = request.args.get('q', '').strip()
    if not q:
        return '', 204

    from collections import defaultdict
    tasks = (
        Task.query
        .options(joinedload(Task.assigned_to), joinedload(Task.department))
        .filter(
            Task.is_archived == False,
            Task.title.ilike(f'%{q}%'),
        )
        .order_by(Task.updated_at.desc(), Task.id.desc())
        .limit(300)
        .all()
    )

    tasks_by_status = defaultdict(list)
    for t in tasks:
        tasks_by_status[t.status].append(t)

    task_ids = [t.id for t in tasks]
    secs_by_task = _build_secs(task_ids)

    active_logs = []
    if task_ids:
        active_logs = (
            TimeLog.query
            .options(joinedload(TimeLog.user))
            .filter(TimeLog.task_id.in_(task_ids), TimeLog.ended_at.is_(None))
            .all()
        )
    active_timers_by_task = defaultdict(list)
    for log in active_logs:
        active_timers_by_task[log.task_id].append(log)
    my_active_task_ids = {log.task_id for log in active_logs if log.user_id == current_user.id}

    return render_template(
        'tasks/_search_results.html',
        tasks_by_status=tasks_by_status,
        secs_by_task=secs_by_task,
        active_timers_by_task=active_timers_by_task,
        my_active_task_ids=my_active_task_ids,
        TaskStatus=TaskStatus, Urgency=Urgency, TaskTag=TaskTag,
    )


@tasks_bp.route('/tasks/<int:task_id>')
@login_required
def detail(task_id):
    task = (Task.query
            .options(joinedload(Task.assigned_to), joinedload(Task.created_by), joinedload(Task.department))
            .get_or_404(task_id))
    logs = (TimeLog.query
            .options(joinedload(TimeLog.user))
            .filter_by(task_id=task_id)
            .order_by(TimeLog.started_at.desc()).all())
    # 1 запрос вместо 2: активный таймер текущего пользователя (для любой задачи и для этой)
    my_active_logs = TimeLog.query.filter_by(user_id=current_user.id, ended_at=None).all()
    active_log = my_active_logs[0] if my_active_logs else None
    my_active = next((l for l in my_active_logs if l.task_id == task_id), None)
    subtasks = (Task.query
                .options(joinedload(Task.assigned_to))
                .filter_by(parent_task_id=task_id, is_archived=False).all())
    parent_task = Task.query.get(task.parent_task_id) if task.parent_task_id else None
    users = (User.query
             .filter_by(is_active=True)
             .filter(User.role != 'tv')
             .order_by(User.full_name)
             .all())
    # Активные таймеры и суммарное время — из уже загруженных logs (без доп. запросов)
    active_timers = [l for l in logs if l.ended_at is None]
    _now = datetime.utcnow()
    task_total_seconds = int(sum(
        ((l.ended_at or _now) - l.started_at).total_seconds() for l in logs
    ))
    from blueprints.analytics import TYPE_LABELS
    return render_template('tasks/detail.html', task=task, logs=logs,
                           active_log=active_log, my_active=my_active,
                           active_timers=active_timers,
                           task_total_seconds=task_total_seconds,
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
    _save_attachments(files, parent.id, task=parent)
    db.session.commit()
    flash('Создана публикация: родительская задача + 2 подзадачи', 'success')
    return parent.id


@tasks_bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create():
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        if request.form.get('create_mode') == 'publication':
            task_id = _create_publication(
                request.form,
                request.files.getlist('attachments'),
                current_user.id,
            )
            url = url_for('tasks.detail', task_id=task_id)
            return jsonify({'ok': True, 'redirect': url}) if is_xhr else redirect(url)
        if not request.form.get('task_type'):
            msg = 'Выберите тип задачи — это обязательное поле'
            if is_xhr:
                return jsonify({'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('tasks.create', **request.args))
        task = _task_from_form(request.form, created_by_id=current_user.id)
        db.session.add(task)
        db.session.flush()
        _save_attachments(request.files.getlist('attachments'), task.id, task=task)
        db.session.commit()
        url = url_for('tasks.detail', task_id=task.id, new=1)
        if is_xhr:
            return jsonify({'ok': True, 'redirect': url})
        flash('Задача создана', 'success')
        return redirect(url)
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
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    task = Task.query.get_or_404(task_id)
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        if not request.form.get('task_type'):
            msg = 'Выберите тип задачи — это обязательное поле'
            if is_xhr:
                return jsonify({'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('tasks.edit', task_id=task_id))
        _task_from_form(request.form, task=task)
        _save_attachments(request.files.getlist('attachments'), task.id, task=task)
        touch(task)
        db.session.commit()
        url = url_for('tasks.detail', task_id=task_id)
        if is_xhr:
            return jsonify({'ok': True, 'redirect': url})
        flash('Задача обновлена', 'success')
        return redirect(url)
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


# ---------- Unified transition API ----------

@tasks_bp.route('/tasks/<int:task_id>/transition', methods=['POST'])
@login_required
def transition(task_id):
    """Single endpoint for all card status transitions (kanban + detail page)."""
    data = request.get_json() or {}
    to_status = data.get('to')
    force = bool(data.get('force', False))

    if to_status not in TaskStatus.LABELS:
        return jsonify({'error': 'Неверный статус'}), 400

    task = Task.query.options(joinedload(Task.assigned_to)).get_or_404(task_id)
    now = datetime.utcnow()

    is_assignee = task.assigned_to_id == current_user.id
    is_free = task.assigned_to_id is None
    can_admin = current_user.can_admin

    # Заявки без типа нельзя перевести ни в какой статус, кроме NEW
    if task.is_external and not task.task_type and to_status != TaskStatus.NEW:
        return jsonify({'error': 'need_task_type', 'task_id': task_id}), 400

    # ── → IN_PROGRESS ────────────────────────────────────────────────────────
    if to_status == TaskStatus.IN_PROGRESS:
        # Чужая задача — запрещено для staff/admin (не manager+)
        if not is_free and not is_assignee and not can_admin:
            return jsonify({'taken': True, 'by': task.assigned_to.full_name})

        # Уже запущена для этого пользователя — идемпотентно
        my_active_here = TimeLog.query.filter_by(
            task_id=task_id, user_id=current_user.id, ended_at=None
        ).first()
        if my_active_here:
            return jsonify({'ok': True, 'already_running': True})

        # Конфликт: у пользователя активен таймер на другой задаче
        active = (TimeLog.query
                 .options(joinedload(TimeLog.task))
                 .filter_by(user_id=current_user.id, ended_at=None)
                 .first())

        forced_prev_task_id = None
        forced_prev_status = None

        if active and active.task_id != task_id:
            if not force:
                return jsonify({
                    'conflict': True,
                    'active_task_id': active.task_id,
                    'active_task_title': active.task.title,
                })
            # Force: остановить старый таймер, поставить старую задачу на паузу
            forced_prev_task_id = active.task_id
            prev_task = active.task
            active.ended_at = now
            # autoflush учтёт ended_at при следующем запросе
            remaining = TimeLog.query.filter_by(task_id=forced_prev_task_id, ended_at=None).first()
            if not remaining:
                prev_task.status = TaskStatus.PAUSED
            forced_prev_status = prev_task.status
            touch(prev_task)

        log = TimeLog(task_id=task_id, user_id=current_user.id, started_at=now)
        db.session.add(log)
        task.status = TaskStatus.IN_PROGRESS
        task.assigned_to_id = current_user.id
        task.completed_at = None
        touch(task)
        db.session.commit()

        return jsonify({
            'ok': True,
            'started_at': log.started_at.isoformat(),
            'prev_task_id': forced_prev_task_id,
            'prev_task_status': forced_prev_status,
        })

    # ── → PAUSED ─────────────────────────────────────────────────────────────
    elif to_status == TaskStatus.PAUSED:
        if task.status == TaskStatus.DONE:
            # Из DONE: любой пользователь может взять задачу на паузу, становясь исполнителем
            task.assigned_to_id = current_user.id
            task.completed_at = None
        elif is_free or task.status == TaskStatus.NEW:
            # Свободная / новая задача → только manager+ может взять на паузу
            if not can_admin:
                return jsonify({'error': 'Нет прав'}), 403
            task.assigned_to_id = current_user.id
        elif not is_assignee and not can_admin:
            return jsonify({'error': 'Нет прав'}), 403

        TimeLog.query.filter_by(task_id=task_id, ended_at=None).update(
            {'ended_at': now}, synchronize_session=False
        )
        task.status = TaskStatus.PAUSED
        touch(task)
        db.session.commit()
        return jsonify({'ok': True})

    # ── → DONE ───────────────────────────────────────────────────────────────
    elif to_status == TaskStatus.DONE:
        if not is_assignee and not can_admin:
            return jsonify({'error': 'Нет прав для завершения задачи'}), 403

        open_count = Task.query.filter(
            Task.parent_task_id == task_id,
            Task.status != TaskStatus.DONE,
            Task.is_archived == False,
        ).count()
        if open_count > 0:
            return jsonify({'error': f'Нельзя закрыть: {open_count} подзадач ещё не выполнены'}), 400

        TimeLog.query.filter_by(task_id=task_id, ended_at=None).update(
            {'ended_at': now}, synchronize_session=False
        )
        task.status = TaskStatus.DONE
        task.completed_at = now
        task.assigned_to_id = None
        touch(task)
        db.session.commit()
        return jsonify({'ok': True})

    # ── → NEW ────────────────────────────────────────────────────────────────
    elif to_status == TaskStatus.NEW:
        if not can_admin:
            return jsonify({'error': 'Нет прав для возврата в «Новые»'}), 403

        TimeLog.query.filter_by(task_id=task_id, ended_at=None).update(
            {'ended_at': now}, synchronize_session=False
        )
        task.status = TaskStatus.NEW
        task.assigned_to_id = None
        task.completed_at = None
        touch(task)
        db.session.commit()
        return jsonify({'ok': True})

    return jsonify({'error': 'Неверный переход'}), 400


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




@tasks_bp.route('/tasks/<int:task_id>/unassign', methods=['POST'])
@login_required
def unassign_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.assigned_to_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403

    TimeLog.query.filter_by(task_id=task_id, ended_at=None).update(
        {'ended_at': datetime.utcnow()}, synchronize_session=False
    )
    task.assigned_to_id = None
    task.status = TaskStatus.NEW
    touch(task)
    db.session.commit()
    return jsonify({'success': True})




@tasks_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    from models import TaskAttachment, CommentAttachment, TaskComment
    # Look up original name from DB for correct download filename
    att = TaskAttachment.query.filter_by(filename=filename).first()
    if att and att.original_name:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], filename,
            download_name=att.original_name
        )
    catt = CommentAttachment.query.filter_by(filename=filename).first()
    if catt and catt.original_name:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], filename,
            download_name=catt.original_name
        )
    # Legacy: single-file comment attachment
    legacy = TaskComment.query.filter_by(filename=filename).first()
    if legacy and legacy.original_name:
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], filename,
            download_name=legacy.original_name
        )
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
    # Удаляем локальный файл (если есть)
    if att.filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
        if os.path.exists(path):
            os.remove(path)
    # Удаляем с Я.Диска (если есть)
    if att.yadisk_path:
        token = current_app.config.get('YANDEX_DISK_TOKEN')
        if token:
            try:
                from services.yandex_disk import delete_file
                delete_file(token, att.yadisk_path)
            except Exception as e:
                current_app.logger.warning(f'YDisk delete failed: {e}')
    db.session.delete(att)
    db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _error(msg, status=400):
        if is_xhr:
            return jsonify({'error': msg}), status
        flash(msg, 'warning')
        return redirect(url_for('tasks.detail', task_id=task_id))

    def _ok():
        if is_xhr:
            return jsonify({'ok': True})
        return redirect(url_for('tasks.detail', task_id=task_id))

    task = Task.query.get_or_404(task_id)
    text = request.form.get('text', '').strip()
    files = [f for f in request.files.getlist('files') if f and f.filename]

    if not text and not files:
        return _error('Комментарий не может быть пустым')

    comment = TaskComment(task_id=task_id, user_id=current_user.id, text=text or None)
    db.session.add(comment)
    db.session.flush()

    if files:
        ydisk_token = current_app.config.get('YANDEX_DISK_TOKEN')
        if ydisk_token and is_xhr:
            # ── Сохраняем во временную директорию, фоновый поток грузит на YDisk ──
            tmp_dir = tempfile.mkdtemp(prefix='gw_yd_')
            temp_files = []
            for f in files:
                ext = os.path.splitext(f.filename)[1].lower()
                tmp_path = os.path.join(tmp_dir, f'{uuid.uuid4().hex}{ext}')
                f.seek(0)
                f.save(tmp_path)
                temp_files.append((tmp_path, f.filename))

            job_id = uuid.uuid4().hex
            with _jobs_lock:
                _ydisk_jobs[job_id] = {
                    'status': 'pending',
                    'total': len(temp_files),
                    'done': 0,
                    'current_file': '',
                    'error': None,
                }

            db.session.commit()  # коммитим комментарий до запуска треда

            app = current_app._get_current_object()
            tz = current_app.config.get('TZ_OFFSET_HOURS', 3)
            t = threading.Thread(
                target=_bg_upload_to_ydisk,
                args=(app, job_id, comment.id, temp_files,
                      ydisk_token, task.id, task.title,
                      current_user.full_name, tz),
                daemon=True,
            )
            t.start()
            return jsonify({'job_id': job_id, 'total': len(temp_files), 'comment_id': comment.id})
        elif ydisk_token:
            # Не-XHR (редкий случай): синхронная загрузка на YDisk
            try:
                from services.yandex_disk import upload_comment_files
                tz = current_app.config.get('TZ_OFFSET_HOURS', 3)
                files_info = [(f, f.filename) for f in files]
                file_results, folder_url = upload_comment_files(
                    token=ydisk_token, task=task, user=current_user,
                    files_info=files_info, tz_offset=tz,
                )
                for res in file_results:
                    db.session.add(CommentAttachment(
                        comment_id=comment.id,
                        original_name=res['original_name'],
                        yadisk_url=res['yadisk_url'],
                        yadisk_path=res['yadisk_path'],
                        yadisk_folder_url=folder_url,
                    ))
            except Exception as e:
                current_app.logger.error(f'YDisk comment upload failed: {e}')
                for f in files:
                    ext = os.path.splitext(f.filename)[1].lower()
                    fname = f'{uuid.uuid4().hex}{ext}'
                    f.seek(0)
                    f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                    db.session.add(CommentAttachment(
                        comment_id=comment.id, filename=fname, original_name=f.filename,
                    ))
        else:
            # YDisk не настроен — сохраняем локально
            for f in files:
                ext = os.path.splitext(f.filename)[1].lower()
                fname = f'{uuid.uuid4().hex}{ext}'
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                db.session.add(CommentAttachment(
                    comment_id=comment.id, filename=fname, original_name=f.filename,
                ))

    db.session.commit()
    return _ok()


@tasks_bp.route('/tasks/<int:task_id>/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(task_id, comment_id):
    comment = TaskComment.query.filter_by(id=comment_id, task_id=task_id).first_or_404()
    if comment.user_id != current_user.id and not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403

    atts = comment.attachments.all()

    # Удаляем с Я.Диска (папки комментариев)
    ydisk_paths = [a.yadisk_path for a in atts if a.yadisk_path]
    if ydisk_paths:
        token = current_app.config.get('YANDEX_DISK_TOKEN')
        if token:
            try:
                from services.yandex_disk import delete_comment_files
                delete_comment_files(token, ydisk_paths)
            except Exception as e:
                current_app.logger.warning(f'YDisk comment delete failed: {e}')

    # Удаляем локальные файлы
    if comment.filename:
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], comment.filename)
        if os.path.exists(path):
            os.remove(path)
    for att in atts:
        if att.filename:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.filename)
            if os.path.exists(path):
                os.remove(path)

    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})


@tasks_bp.route('/tasks/<int:task_id>/upload-status/<string:job_id>')
@login_required
def upload_status(task_id, job_id):
    """Polling endpoint: статус фоновой загрузки файлов на Яндекс Диск."""
    with _jobs_lock:
        job = _ydisk_jobs.get(job_id)
    if not job:
        # Job потерян (сервер перезапустился). Проверяем по comment_id —
        # сохранились ли вложения в БД.
        from models import TaskComment as _TC
        comment_id = request.args.get('comment_id', type=int)
        if comment_id:
            comment_obj = _TC.query.get(comment_id)
            if comment_obj and comment_obj.attachments.count() > 0:
                # Вложения есть — поток успел завершиться до перезапуска
                return jsonify({'status': 'complete'})
            # Вложений нет — откатываем комментарий
            if comment_obj:
                try:
                    db.session.delete(comment_obj)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return jsonify({'status': 'error',
                            'error': 'Загрузка прервана (сервер был перезапущен)'})
        return jsonify({'status': 'error',
                        'error': 'Загрузка прервана (сервер был перезапущен)'})
    return jsonify({
        'status': job['status'],
        'total': job['total'],
        'done': job['done'],
        'current_file': job.get('current_file', ''),
        'error': job.get('error'),
    })


@tasks_bp.route('/tasks/<int:task_id>/card')
@login_required
def task_card(task_id):
    from collections import defaultdict
    from sqlalchemy import func as sqlfunc
    task = (Task.query
            .options(joinedload(Task.assigned_to), joinedload(Task.department))
            .get_or_404(task_id))
    active_logs = TimeLog.query.options(joinedload(TimeLog.user)).filter_by(task_id=task_id, ended_at=None).all()
    active_timers_by_task = defaultdict(list)
    for log in active_logs:
        active_timers_by_task[log.task_id].append(log)
    my_active_task_ids = {log.task_id for log in active_logs if log.user_id == current_user.id}
    now = datetime.utcnow()
    secs = db.session.query(sqlfunc.coalesce(sqlfunc.sum(
        sqlfunc.extract('epoch', sqlfunc.coalesce(TimeLog.ended_at, now) - TimeLog.started_at)
    ), 0)).filter(TimeLog.task_id == task_id).scalar() or 0
    secs_by_task = {task_id: int(secs)}
    return render_template('tasks/_card.html', task=task,
                           Urgency=Urgency, TaskStatus=TaskStatus, TaskTag=TaskTag,
                           my_active_task_ids=my_active_task_ids,
                           active_timers_by_task=active_timers_by_task,
                           secs_by_task=secs_by_task)


@tasks_bp.route('/tasks/my-timer')
@login_required
def my_timer():
    active = TimeLog.query.filter_by(user_id=current_user.id, ended_at=None).first()
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
    count = Task.query.filter(
        Task.status == TaskStatus.DONE,
        Task.is_archived == False,
    ).update({'is_archived': True, 'archived_at': now}, synchronize_session=False)
    db.session.commit()
    return jsonify({'ok': True, 'count': count})


@tasks_bp.route('/tasks/game/score', methods=['POST'])
@login_required
def game_save_score():
    data = request.get_json(silent=True) or {}
    new_score = int(data.get('score', 0))
    gs = GameScore.query.filter_by(user_id=current_user.id).first()
    if gs is None:
        gs = GameScore(user_id=current_user.id, score=new_score)
        db.session.add(gs)
    elif new_score > gs.score:
        gs.score = new_score
        gs.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'ok': True, 'best': gs.score})


@tasks_bp.route('/tasks/game/leaderboard')
@login_required
def game_leaderboard():
    rows = db.session.query(GameScore, User)\
        .join(User, GameScore.user_id == User.id)\
        .filter(User.is_active == True)\
        .order_by(GameScore.score.desc())\
        .limit(10).all()
    return jsonify([{
        'name': u.full_name or u.username,
        'score': gs.score,
        'is_me': gs.user_id == current_user.id
    } for gs, u in rows])


@tasks_bp.route('/tasks/game/session/start', methods=['POST'])
@login_required
def game_session_start():
    task = Task(
        title='Рефлексирование',
        status=TaskStatus.IN_PROGRESS,
        created_by_id=current_user.id,
        assigned_to_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'ok': True, 'task_id': task.id})


@tasks_bp.route('/tasks/game/session/end', methods=['POST'])
@login_required
def game_session_end():
    data = request.get_json(silent=True) or {}
    task_id = data.get('task_id')
    if not task_id:
        return jsonify({'ok': False}), 400
    task = Task.query.filter_by(id=task_id, assigned_to_id=current_user.id).first()
    if not task:
        return jsonify({'ok': False}), 404
    task.status = TaskStatus.DONE
    task.completed_at = datetime.utcnow()
    task.assigned_to_id = None
    db.session.commit()
    return jsonify({'ok': True})


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
    # Bulk delete time_logs вместо поштучного удаления
    TimeLog.query.filter_by(task_id=task_id).delete(synchronize_session=False)
    # Bulk update subtasks и планов
    Task.query.filter_by(parent_task_id=task_id).update(
        {'parent_task_id': None}, synchronize_session=False
    )
    from models import Plan
    Plan.query.filter_by(converted_task_id=task_id).update(
        {'converted_task_id': None}, synchronize_session=False
    )
    db.session.delete(task)
    db.session.commit()
    flash('Задача удалена', 'success')
    return redirect(url_for('tasks.list_tasks'))
