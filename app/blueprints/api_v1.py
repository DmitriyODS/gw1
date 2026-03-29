"""
Groove Work REST API v1
Prefix: /api/v1
Auth:   Bearer JWT (flask-jwt-extended)
Docs:   GET /api/v1/docs
Spec:   GET /api/v1/openapi.json
"""
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    current_user as jwt_user,
)
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import joinedload
from extensions import db
from models import (
    Task, User, Department, TaskType, TaskStatus, Urgency,
    TimeLog, TaskComment, Role,
    Plan, PlanGroup, Rhythm, RhythmFrequency, TaskTag,
)

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# ── Serializers ───────────────────────────────────────────────────────────────

def _user(u):
    if not u:
        return None
    return {
        'id': u.id,
        'username': u.username,
        'full_name': u.full_name,
        'role': u.role,
        'is_active': u.is_active,
        'avatar_url': f'/api/avatar/{u.id}',
    }


def _task(task, secs=None, detail=False):
    d = {
        'id': task.id,
        'title': task.title,
        'status': task.status,
        'urgency': task.urgency,
        'task_type': task.task_type,
        'tags': task.tags or [],
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'is_archived': task.is_archived,
        'is_external': task.is_external,
        'is_overdue': task.is_overdue,
        'parent_task_id': task.parent_task_id,
        'created_at': task.created_at.isoformat() if task.created_at else None,
        'updated_at': task.updated_at.isoformat() if task.updated_at else None,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        'department': (
            {'id': task.department.id, 'name': task.department.name}
            if task.department else None
        ),
        'created_by': _user(task.created_by),
        'assigned_to': _user(task.assigned_to),
        'total_seconds': secs if secs is not None else task.total_seconds,
    }
    if detail:
        d.update({
            'description': task.description,
            'customer_name': task.customer_name,
            'customer_phone': task.customer_phone,
            'customer_email': task.customer_email,
            'dynamic_fields': task.dynamic_fields or {},
            'attachments': [
                {
                    'id': a.id,
                    'original_name': a.original_name,
                    'download_url': f'/uploads/{a.filename}',
                    'yadisk_url': a.yadisk_url,
                    'uploaded_at': a.uploaded_at.isoformat() if a.uploaded_at else None,
                }
                for a in task.attachments
            ],
            'comments': [_comment(c) for c in task.comments],
            'subtasks': [
                {
                    'id': s.id,
                    'title': s.title,
                    'status': s.status,
                    'urgency': s.urgency,
                    'task_type': s.task_type,
                    'assigned_to': _user(s.assigned_to),
                    'total_seconds': s.total_seconds,
                }
                for s in task.subtasks
            ],
        })
    return d


def _comment(c):
    return {
        'id': c.id,
        'text': c.text,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'user': _user(c.user),
        'attachments': [
            {
                'id': a.id,
                'original_name': a.original_name,
                'download_url': f'/uploads/{a.filename}',
                'yadisk_url': a.yadisk_url,
            }
            for a in c.attachments
        ],
    }


def _ok(data=None, meta=None, code=200):
    resp = {'data': data}
    if meta is not None:
        resp['meta'] = meta
    return jsonify(resp), code


def _err(msg, code=400):
    return jsonify({'error': msg}), code


def _secs_for(task_ids):
    """One-shot seconds aggregate for a list of task IDs."""
    if not task_ids:
        return {}
    now = datetime.utcnow()
    rows = (
        db.session.query(
            TimeLog.task_id,
            sqlfunc.coalesce(
                sqlfunc.sum(
                    sqlfunc.extract(
                        'epoch',
                        sqlfunc.coalesce(TimeLog.ended_at, now) - TimeLog.started_at,
                    )
                ),
                0,
            ).label('secs'),
        )
        .filter(TimeLog.task_id.in_(task_ids))
        .group_by(TimeLog.task_id)
        .all()
    )
    return {r.task_id: int(r.secs) for r in rows}


def _parse_deadline(raw):
    """Parse ISO 8601 deadline string to naive UTC datetime."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if dt.tzinfo:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        raise ValueError('Неверный формат deadline (ISO 8601)')


# ── Auth ──────────────────────────────────────────────────────────────────────

@api_v1_bp.post('/auth/login')
def auth_login():
    """Авторизация. Возвращает access + refresh токены."""
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return _err('username и password обязательны')
    user = User.query.filter_by(username=username, is_active=True).first()
    if not user or not user.check_password(password):
        return _err('Неверный логин или пароль', 401)
    return _ok({
        'access_token': create_access_token(identity=str(user.id)),
        'refresh_token': create_refresh_token(identity=str(user.id)),
        'user': _user(user),
    })


@api_v1_bp.post('/auth/refresh')
@jwt_required(refresh=True)
def auth_refresh():
    """Обновить access-токен (передать refresh в Authorization: Bearer ...)."""
    return _ok({'access_token': create_access_token(identity=get_jwt_identity())})


@api_v1_bp.get('/auth/me')
@jwt_required()
def auth_me():
    """Текущий пользователь."""
    return _ok(_user(jwt_user))


# ── Tasks ─────────────────────────────────────────────────────────────────────

@api_v1_bp.get('/tasks')
@jwt_required()
def tasks_list():
    """
    Список задач с пагинацией.

    Query params:
      page         int  (default 1)
      per_page     int  (default 20, max 100)
      status       str  comma-separated: new,in_progress,paused,done
      urgency      str  slow|normal|important|urgent
      department_id int
      assigned_to_id int  (pass "me" for current user)
      task_type    str
      is_archived  bool (default false)
      search       str  поиск по названию (ILIKE)
    """
    page = max(1, request.args.get('page', 1, int))
    per_page = min(100, max(1, request.args.get('per_page', 20, int)))

    q = Task.query.options(
        joinedload(Task.assigned_to),
        joinedload(Task.created_by),
        joinedload(Task.department),
    )

    # --- filters ---
    statuses_raw = request.args.get('status', '')
    if statuses_raw:
        status_list = [s.strip() for s in statuses_raw.split(',') if s.strip()]
        q = q.filter(Task.status.in_(status_list))

    is_archived = request.args.get('is_archived', 'false').lower() in ('true', '1')
    q = q.filter(Task.is_archived == is_archived)

    urgency = request.args.get('urgency')
    if urgency:
        q = q.filter(Task.urgency == urgency)

    dept_id = request.args.get('department_id', type=int)
    if dept_id:
        q = q.filter(Task.department_id == dept_id)

    assigned_raw = request.args.get('assigned_to_id', '')
    if assigned_raw == 'me':
        q = q.filter(Task.assigned_to_id == jwt_user.id)
    elif assigned_raw:
        try:
            q = q.filter(Task.assigned_to_id == int(assigned_raw))
        except ValueError:
            pass

    task_type = request.args.get('task_type')
    if task_type:
        q = q.filter(Task.task_type == task_type)

    parent_task_id = request.args.get('parent_task_id', type=int)
    if parent_task_id:
        q = q.filter(Task.parent_task_id == parent_task_id)

    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(Task.title.ilike(f'%{search}%'))

    # --- sort: по updated_at desc ---
    q = q.order_by(Task.updated_at.desc(), Task.id.desc())

    total = q.count()
    tasks = q.offset((page - 1) * per_page).limit(per_page).all()
    secs = _secs_for([t.id for t in tasks])

    return _ok(
        [_task(t, secs=secs.get(t.id, 0)) for t in tasks],
        meta={
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page if per_page else 1,
        },
    )


@api_v1_bp.get('/tasks/<int:task_id>')
@jwt_required()
def task_get(task_id):
    """Задача с комментариями и вложениями."""
    task = (
        Task.query
        .options(
            joinedload(Task.assigned_to),
            joinedload(Task.created_by),
            joinedload(Task.department),
        )
        .get_or_404(task_id)
    )
    secs_map = _secs_for([task_id])
    return _ok(_task(task, secs=secs_map.get(task_id, 0), detail=True))


@api_v1_bp.post('/tasks')
@jwt_required()
def task_create():
    """
    Создать задачу.

    Body (JSON):
      title*       str
      task_type*   str  (slug из /api/v1/task-types)
      description  str
      urgency      str  slow|normal|important|urgent
      deadline     str  ISO 8601
      department_id int
      tags         [str]
      dynamic_fields {}
      customer_name str
      customer_phone str
      customer_email str
      parent_task_id int
    """
    body = request.get_json(silent=True) or {}
    title = (body.get('title') or '').strip()
    task_type = (body.get('task_type') or '').strip()
    if not title:
        return _err('title обязателен')
    if not task_type:
        return _err('task_type обязателен')

    try:
        deadline = _parse_deadline(body.get('deadline'))
    except ValueError as e:
        return _err(str(e))

    urgency = body.get('urgency', Urgency.NORMAL)
    if urgency not in Urgency.ORDER:
        return _err(f'urgency должен быть одним из: {list(Urgency.ORDER)}')

    task = Task(
        title=title,
        description=(body.get('description') or '').strip() or None,
        task_type=task_type,
        urgency=urgency,
        deadline=deadline,
        department_id=body.get('department_id'),
        tags=body.get('tags') or [],
        dynamic_fields=body.get('dynamic_fields') or {},
        customer_name=(body.get('customer_name') or '').strip() or None,
        customer_phone=(body.get('customer_phone') or '').strip() or None,
        customer_email=(body.get('customer_email') or '').strip() or None,
        parent_task_id=body.get('parent_task_id'),
        created_by_id=jwt_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return _ok(_task(task, secs=0, detail=True), code=201)


@api_v1_bp.patch('/tasks/<int:task_id>')
@jwt_required()
def task_update(task_id):
    """
    Обновить задачу (частичное обновление).
    Принимает любые поля из task_create.
    """
    task = Task.query.get_or_404(task_id)
    if (
        task.assigned_to_id != jwt_user.id
        and task.created_by_id != jwt_user.id
        and not jwt_user.can_admin
    ):
        return _err('Нет прав для редактирования', 403)

    body = request.get_json(silent=True) or {}
    if 'title' in body:
        task.title = (body['title'] or '').strip()
    if 'description' in body:
        task.description = (body['description'] or '').strip() or None
    if 'task_type' in body:
        task.task_type = body['task_type']
    if 'urgency' in body:
        task.urgency = body['urgency']
    if 'department_id' in body:
        task.department_id = body['department_id']
    if 'tags' in body:
        task.tags = body['tags']
    if 'dynamic_fields' in body:
        task.dynamic_fields = body['dynamic_fields']
    if 'customer_name' in body:
        task.customer_name = (body['customer_name'] or '').strip() or None
    if 'customer_phone' in body:
        task.customer_phone = (body['customer_phone'] or '').strip() or None
    if 'customer_email' in body:
        task.customer_email = (body['customer_email'] or '').strip() or None
    if 'deadline' in body:
        try:
            task.deadline = _parse_deadline(body['deadline'])
        except ValueError as e:
            return _err(str(e))

    task.updated_at = datetime.utcnow()
    db.session.commit()
    secs_map = _secs_for([task_id])
    return _ok(_task(task, secs=secs_map.get(task_id, 0), detail=True))


@api_v1_bp.delete('/tasks/<int:task_id>')
@jwt_required()
def task_delete(task_id):
    """Удалить задачу (только admin+)."""
    if not jwt_user.can_admin:
        return _err('Нет прав для удаления', 403)
    task = Task.query.get_or_404(task_id)
    upload_folder = current_app.config['UPLOAD_FOLDER']

    for att in task.attachments.all():
        try:
            os.remove(os.path.join(upload_folder, att.filename))
        except OSError:
            pass
        db.session.delete(att)

    for log in task.time_logs.all():
        db.session.delete(log)

    for comment in task.comments.all():
        for ca in comment.attachments.all():
            try:
                os.remove(os.path.join(upload_folder, ca.filename))
            except OSError:
                pass
        db.session.delete(comment)

    Task.query.filter_by(parent_task_id=task_id).update({'parent_task_id': None})
    db.session.delete(task)
    db.session.commit()
    return _ok({'deleted': task_id})


@api_v1_bp.post('/tasks/<int:task_id>/archive')
@jwt_required()
def task_archive(task_id):
    """Архивировать / разархивировать задачу (только manager+)."""
    if not jwt_user.can_admin:
        return _err('Нет прав', 403)
    task = Task.query.get_or_404(task_id)
    task.is_archived = not task.is_archived
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return _ok({'archived': task.is_archived})


@api_v1_bp.post('/tasks/<int:task_id>/assign')
@jwt_required()
def task_assign(task_id):
    """
    Делегировать задачу другому исполнителю (только manager+).
    Body: {user_id: int | null}
    """
    if not jwt_user.can_admin:
        return _err('Нет прав', 403)
    task = Task.query.get_or_404(task_id)
    body = request.get_json(silent=True) or {}
    user_id = body.get('user_id')
    if user_id is not None:
        user = db.session.get(User, user_id)
        if not user:
            return _err('Пользователь не найден', 404)
        task.assigned_to_id = user_id
    else:
        task.assigned_to_id = None
    task.updated_at = datetime.utcnow()
    db.session.commit()
    secs_map = _secs_for([task_id])
    return _ok(_task(task, secs=secs_map.get(task_id, 0), detail=True))


@api_v1_bp.post('/tasks/<int:task_id>/done')
@jwt_required()
def task_done(task_id):
    """Завершить задачу."""
    task = Task.query.get_or_404(task_id)
    if task.is_external and not task.task_type:
        return _err('Укажите тип задачи перед закрытием')
    if task.open_subtasks_count > 0:
        return _err(f'Есть открытые подзадачи: {task.open_subtasks_count}')
    now = datetime.utcnow()
    TimeLog.query.filter_by(task_id=task_id, ended_at=None).update({'ended_at': now})
    task.status = TaskStatus.DONE
    task.completed_at = now
    task.assigned_to_id = None
    task.updated_at = now
    db.session.commit()
    return _ok({'done': True, 'completed_at': now.isoformat()})


# ── Timer ─────────────────────────────────────────────────────────────────────

@api_v1_bp.post('/tasks/<int:task_id>/timer/start')
@jwt_required()
def timer_start(task_id):
    """
    Запустить таймер.

    Body (JSON):
      force  bool  — остановить текущий активный таймер и переключиться

    Ответы:
      {started: true}                       — таймер запущен
      {conflict: "taken", by: "Имя"}        — задача занята другим
      {conflict: "busy",                    — у вас другой активный таймер
       active_task_id, active_task_title}
      {already_running: true}               — таймер уже запущен
    """
    task = Task.query.get_or_404(task_id)
    if task.is_archived:
        return _err('Задача в архиве')
    if task.status == TaskStatus.DONE:
        return _err('Задача уже выполнена')
    if task.is_external and not task.task_type:
        return _err('Укажите тип задачи перед началом работы')

    force = (request.get_json(silent=True) or {}).get('force', False)
    now = datetime.utcnow()

    # Кто-то другой работает над этой задачей?
    other_log = (
        TimeLog.query
        .filter(
            TimeLog.task_id == task_id,
            TimeLog.user_id != jwt_user.id,
            TimeLog.ended_at.is_(None),
        )
        .first()
    )
    if other_log:
        other = db.session.get(User, other_log.user_id)
        return _ok({'conflict': 'taken', 'by': other.full_name if other else 'Другой сотрудник'})

    # У текущего пользователя уже запущен таймер на другой задаче?
    my_active = TimeLog.query.filter_by(user_id=jwt_user.id, ended_at=None).first()
    if my_active and my_active.task_id != task_id:
        if not force:
            other_task = db.session.get(Task, my_active.task_id)
            return _ok({
                'conflict': 'busy',
                'active_task_id': my_active.task_id,
                'active_task_title': other_task.title if other_task else None,
            })
        # force: остановить текущий таймер
        my_active.ended_at = now
        other_task = db.session.get(Task, my_active.task_id)
        if other_task:
            still_running = TimeLog.query.filter(
                TimeLog.task_id == other_task.id,
                TimeLog.ended_at.is_(None),
            ).first()
            if not still_running:
                other_task.status = TaskStatus.PAUSED
                other_task.updated_at = now

    # Уже запущен на этой задаче?
    already = TimeLog.query.filter_by(
        task_id=task_id, user_id=jwt_user.id, ended_at=None
    ).first()
    if already:
        return _ok({'already_running': True})

    log = TimeLog(task_id=task_id, user_id=jwt_user.id, started_at=now)
    db.session.add(log)
    task.status = TaskStatus.IN_PROGRESS
    task.assigned_to_id = jwt_user.id
    task.updated_at = now
    db.session.commit()
    return _ok({'started': True, 'started_at': now.isoformat()})


@api_v1_bp.post('/tasks/<int:task_id>/timer/pause')
@jwt_required()
def timer_pause(task_id):
    """Поставить таймер на паузу."""
    task = Task.query.get_or_404(task_id)
    log = TimeLog.query.filter_by(
        task_id=task_id, user_id=jwt_user.id, ended_at=None
    ).first()
    if not log:
        return _err('Таймер не запущен', 400)

    now = datetime.utcnow()
    log.ended_at = now

    still_running = TimeLog.query.filter(
        TimeLog.task_id == task_id,
        TimeLog.ended_at.is_(None),
    ).first()
    if not still_running:
        task.status = TaskStatus.PAUSED
        task.updated_at = now

    db.session.commit()
    return _ok({'paused': True, 'task_status': task.status})


@api_v1_bp.get('/tasks/my-timer')
@jwt_required()
def my_timer():
    """Активный таймер текущего пользователя."""
    log = TimeLog.query.filter_by(user_id=jwt_user.id, ended_at=None).first()
    if not log:
        return _ok({'active': False})
    return _ok({
        'active': True,
        'task_id': log.task_id,
        'started_at': log.started_at.isoformat(),
    })


# ── Comments ──────────────────────────────────────────────────────────────────

@api_v1_bp.get('/tasks/<int:task_id>/comments')
@jwt_required()
def comments_list(task_id):
    """Список комментариев задачи."""
    Task.query.get_or_404(task_id)
    comments = (
        TaskComment.query
        .options(joinedload(TaskComment.user))
        .filter_by(task_id=task_id)
        .order_by(TaskComment.created_at)
        .all()
    )
    return _ok([_comment(c) for c in comments])


@api_v1_bp.post('/tasks/<int:task_id>/comments')
@jwt_required()
def comment_create(task_id):
    """Добавить комментарий. Body: {text: str}"""
    Task.query.get_or_404(task_id)
    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    if not text:
        return _err('text обязателен')
    comment = TaskComment(task_id=task_id, user_id=jwt_user.id, text=text)
    db.session.add(comment)
    db.session.commit()
    return _ok(_comment(comment), code=201)


@api_v1_bp.delete('/tasks/<int:task_id>/comments/<int:comment_id>')
@jwt_required()
def comment_delete(task_id, comment_id):
    """Удалить комментарий."""
    comment = TaskComment.query.filter_by(
        id=comment_id, task_id=task_id
    ).first_or_404()
    if comment.user_id != jwt_user.id and not jwt_user.can_admin:
        return _err('Нет прав для удаления', 403)
    db.session.delete(comment)
    db.session.commit()
    return _ok({'deleted': comment_id})


# ── Lookups ───────────────────────────────────────────────────────────────────

@api_v1_bp.get('/task-types')
@jwt_required()
def get_task_types():
    """Типы задач."""
    types = TaskType.query.order_by(TaskType.sort_order, TaskType.label).all()
    return _ok([{'slug': t.slug, 'label': t.label} for t in types])


@api_v1_bp.get('/departments')
@jwt_required()
def get_departments():
    """Подразделения."""
    depts = Department.query.order_by(Department.name).all()
    return _ok([{'id': d.id, 'name': d.name, 'head': d.head} for d in depts])


@api_v1_bp.get('/users')
@jwt_required()
def get_users():
    """Активные пользователи (кроме tv)."""
    users = (
        User.query
        .filter_by(is_active=True)
        .filter(User.role != Role.TV)
        .order_by(User.full_name)
        .all()
    )
    return _ok([_user(u) for u in users])


# ── Plans ─────────────────────────────────────────────────────────────────────

def _plan(p):
    return {
        'id': p.id,
        'title': p.title,
        'description': p.description,
        'task_type': p.task_type,
        'urgency': p.urgency,
        'tags': p.tags or [],
        'dynamic_fields': p.dynamic_fields or {},
        'department': {'id': p.department.id, 'name': p.department.name} if p.department else None,
        'group': {'id': p.group.id, 'name': p.group.name} if p.group else None,
        'release_date': p.release_date.isoformat() if p.release_date else None,
        'is_due': p.is_due,
        'customer_name': p.customer_name,
        'created_by': _user(p.created_by),
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


@api_v1_bp.get('/plans')
@jwt_required()
def plans_list():
    """Список активных планов (не конвертированных)."""
    group_id = request.args.get('group_id', type=int)
    q = Plan.query.filter_by(is_converted=False)
    if group_id:
        q = q.filter_by(group_id=group_id)
    plans = q.order_by(Plan.release_date.asc(), Plan.created_at.desc()).all()
    groups = PlanGroup.query.order_by(PlanGroup.name).all()
    return _ok({
        'plans': [_plan(p) for p in plans],
        'groups': [{'id': g.id, 'name': g.name} for g in groups],
    })


@api_v1_bp.post('/plans')
@jwt_required()
def plan_create():
    """Создать план. Body: {title, task_type, urgency, description, department_id, group_id, release_date, tags}"""
    body = request.get_json(silent=True) or {}
    title = (body.get('title') or '').strip()
    task_type = (body.get('task_type') or '').strip()
    if not title:
        return _err('title обязателен')
    if not task_type:
        return _err('task_type обязателен')
    try:
        release_date = _parse_deadline(body.get('release_date'))
    except ValueError as e:
        return _err(str(e))
    plan = Plan(
        title=title,
        description=(body.get('description') or '').strip() or None,
        task_type=task_type,
        urgency=body.get('urgency', Urgency.NORMAL),
        tags=body.get('tags') or [],
        department_id=body.get('department_id'),
        group_id=body.get('group_id'),
        release_date=release_date,
        customer_name=(body.get('customer_name') or '').strip() or None,
        created_by_id=jwt_user.id,
    )
    db.session.add(plan)
    db.session.commit()
    return _ok(_plan(plan), code=201)


@api_v1_bp.delete('/plans/<int:plan_id>')
@jwt_required()
def plan_delete(plan_id):
    """Удалить план."""
    plan = Plan.query.get_or_404(plan_id)
    if not jwt_user.can_admin and plan.created_by_id != jwt_user.id:
        return _err('Нет прав', 403)
    db.session.delete(plan)
    db.session.commit()
    return _ok({'deleted': plan_id})


@api_v1_bp.post('/plans/<int:plan_id>/push')
@jwt_required()
def plan_push(plan_id):
    """Конвертировать план в задачу (удаляет план)."""
    plan = Plan.query.get_or_404(plan_id)
    tags = list(plan.tags or [])
    if plan.task_type == 'publication' and TaskTag.PUBLICATION not in tags:
        tags.append(TaskTag.PUBLICATION)
    task = Task(
        title=plan.title,
        description=plan.description,
        customer_name=plan.customer_name,
        customer_phone=plan.customer_phone,
        department_id=plan.department_id,
        task_type=plan.task_type,
        urgency=plan.urgency or Urgency.NORMAL,
        tags=tags,
        dynamic_fields=plan.dynamic_fields or {},
        status=TaskStatus.NEW,
        created_by_id=plan.created_by_id or jwt_user.id,
    )
    db.session.add(task)
    db.session.flush()
    if plan.task_type == 'publication':
        db.session.add(Task(
            title=f'[Дизайн] {task.title}', task_type='publication',
            tags=[TaskTag.DESIGN], urgency=task.urgency,
            department_id=task.department_id, parent_task_id=task.id,
            status=TaskStatus.NEW, dynamic_fields={}, created_by_id=jwt_user.id,
        ))
        db.session.add(Task(
            title=f'[Текст] {task.title}', task_type='publication',
            tags=[TaskTag.TEXT], urgency=task.urgency,
            department_id=task.department_id, parent_task_id=task.id,
            status=TaskStatus.NEW, dynamic_fields={}, created_by_id=jwt_user.id,
        ))
    db.session.delete(plan)
    db.session.commit()
    secs_map = _secs_for([task.id])
    return _ok(_task(task, secs=secs_map.get(task.id, 0), detail=True))


@api_v1_bp.post('/plan-groups')
@jwt_required()
def plan_group_create():
    """Создать группу планов. Body: {name}"""
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return _err('name обязателен')
    if PlanGroup.query.filter_by(name=name).first():
        return _err('Группа с таким названием уже существует')
    g = PlanGroup(name=name, created_by_id=jwt_user.id)
    db.session.add(g)
    db.session.commit()
    return _ok({'id': g.id, 'name': g.name}, code=201)


@api_v1_bp.delete('/plan-groups/<int:group_id>')
@jwt_required()
def plan_group_delete(group_id):
    """Удалить группу планов (только manager+)."""
    if not jwt_user.can_admin:
        return _err('Нет прав', 403)
    g = PlanGroup.query.get_or_404(group_id)
    Plan.query.filter_by(group_id=group_id).update({'group_id': None})
    db.session.delete(g)
    db.session.commit()
    return _ok({'deleted': group_id})


# ── Rhythms ───────────────────────────────────────────────────────────────────

def _rhythm(r):
    return {
        'id': r.id,
        'name': r.name,
        'description': r.description,
        'frequency': r.frequency,
        'day_of_week': r.day_of_week,
        'day_of_month': r.day_of_month,
        'trigger_time': r.trigger_time,
        'task_title': r.task_title,
        'task_description': r.task_description,
        'task_type': r.task_type,
        'task_urgency': r.task_urgency,
        'task_tags': r.task_tags or [],
        'department': {'id': r.department.id, 'name': r.department.name} if r.department else None,
        'is_active': r.is_active,
        'is_due': r.is_due,
        'schedule_label': r.schedule_label,
        'last_run_at': r.last_run_at.isoformat() if r.last_run_at else None,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    }


@api_v1_bp.get('/rhythms')
@jwt_required()
def rhythms_list():
    """Список ритмов."""
    rhythms = Rhythm.query.order_by(Rhythm.name).all()
    return _ok([_rhythm(r) for r in rhythms])


@api_v1_bp.post('/rhythms')
@jwt_required()
def rhythm_create():
    """Создать ритм."""
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    task_title = (body.get('task_title') or '').strip()
    task_type = (body.get('task_type') or '').strip()
    if not name:
        return _err('name обязателен')
    if not task_title:
        return _err('task_title обязателен')
    if not task_type:
        return _err('task_type обязателен')
    r = Rhythm(
        name=name,
        description=(body.get('description') or '').strip() or None,
        frequency=body.get('frequency', RhythmFrequency.DAILY),
        day_of_week=body.get('day_of_week'),
        day_of_month=body.get('day_of_month'),
        trigger_time=body.get('trigger_time') or None,
        task_title=task_title,
        task_description=(body.get('task_description') or '').strip() or None,
        task_type=task_type,
        task_urgency=body.get('task_urgency', Urgency.NORMAL),
        task_tags=body.get('task_tags') or [],
        department_id=body.get('department_id'),
        is_active=body.get('is_active', True),
        created_by_id=jwt_user.id,
    )
    db.session.add(r)
    db.session.commit()
    return _ok(_rhythm(r), code=201)


@api_v1_bp.post('/rhythms/<int:rhythm_id>/toggle')
@jwt_required()
def rhythm_toggle(rhythm_id):
    """Включить/выключить ритм."""
    r = Rhythm.query.get_or_404(rhythm_id)
    r.is_active = not r.is_active
    db.session.commit()
    return _ok({'is_active': r.is_active})


@api_v1_bp.post('/rhythms/<int:rhythm_id>/run')
@jwt_required()
def rhythm_run(rhythm_id):
    """Запустить ритм сейчас (создать задачу)."""
    r = Rhythm.query.get_or_404(rhythm_id)
    tags = list(r.task_tags or [])
    task = Task(
        title=r.task_title,
        description=r.task_description,
        task_type=r.task_type,
        tags=tags,
        urgency=r.task_urgency or Urgency.NORMAL,
        department_id=r.department_id,
        status=TaskStatus.NEW,
        created_by_id=jwt_user.id,
        dynamic_fields={},
    )
    db.session.add(task)
    db.session.flush()
    if r.task_type == 'publication':
        from models import TaskTag as TT
        db.session.add(Task(
            title=f'[Дизайн] {task.title}', task_type='publication',
            tags=[TT.DESIGN], urgency=task.urgency,
            department_id=task.department_id, parent_task_id=task.id,
            status=TaskStatus.NEW, dynamic_fields={}, created_by_id=jwt_user.id,
        ))
        db.session.add(Task(
            title=f'[Текст] {task.title}', task_type='publication',
            tags=[TT.TEXT], urgency=task.urgency,
            department_id=task.department_id, parent_task_id=task.id,
            status=TaskStatus.NEW, dynamic_fields={}, created_by_id=jwt_user.id,
        ))
    r.last_run_at = datetime.utcnow()
    db.session.commit()
    return _ok(_task(task, secs=0, detail=False))


@api_v1_bp.delete('/rhythms/<int:rhythm_id>')
@jwt_required()
def rhythm_delete(rhythm_id):
    """Удалить ритм."""
    r = Rhythm.query.get_or_404(rhythm_id)
    db.session.delete(r)
    db.session.commit()
    return _ok({'deleted': rhythm_id})


# ── Analytics ─────────────────────────────────────────────────────────────────

@api_v1_bp.get('/analytics/summary')
@jwt_required()
def analytics_summary():
    """
    Сводная аналитика.
    Query: period=day|week|month|year (default: week)
    """
    from datetime import timedelta
    period = request.args.get('period', 'week')
    tz = current_app.config.get('TZ_OFFSET_HOURS', 3)
    now_utc = datetime.utcnow()
    now_local = now_utc + timedelta(hours=tz)

    if period == 'day':
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_local = (now_local - timedelta(days=now_local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
    elif period == 'month':
        start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'year':
        start_local = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_local = now_local - timedelta(days=7)

    start = start_local - timedelta(hours=tz)

    # Tasks by status in period
    status_rows = (
        db.session.query(Task.status, sqlfunc.count(Task.id))
        .filter(Task.created_at >= start, Task.is_archived == False)
        .group_by(Task.status).all()
    )
    by_status = {s: 0 for s in ['new', 'in_progress', 'paused', 'done']}
    for s, cnt in status_rows:
        if s in by_status:
            by_status[s] = cnt
    total = sum(by_status.values())

    # Tasks by type (top 8)
    type_rows = (
        db.session.query(Task.task_type, sqlfunc.count(Task.id))
        .filter(Task.created_at >= start, Task.is_archived == False)
        .group_by(Task.task_type)
        .order_by(sqlfunc.count(Task.id).desc())
        .limit(8).all()
    )
    by_type = [{'type': t or 'other', 'count': cnt} for t, cnt in type_rows]

    # Total time worked in period (all users)
    time_rows = (
        db.session.query(
            sqlfunc.coalesce(
                sqlfunc.sum(
                    sqlfunc.extract('epoch',
                        sqlfunc.coalesce(TimeLog.ended_at, now_utc) - TimeLog.started_at)
                ), 0
            )
        )
        .filter(TimeLog.started_at >= start)
        .scalar()
    )
    total_seconds = int(time_rows or 0)

    # My time worked
    my_time = (
        db.session.query(
            sqlfunc.coalesce(
                sqlfunc.sum(
                    sqlfunc.extract('epoch',
                        sqlfunc.coalesce(TimeLog.ended_at, now_utc) - TimeLog.started_at)
                ), 0
            )
        )
        .filter(TimeLog.started_at >= start, TimeLog.user_id == jwt_user.id)
        .scalar()
    )
    my_seconds = int(my_time or 0)

    # Top workers by time
    worker_rows = (
        db.session.query(
            TimeLog.user_id,
            sqlfunc.coalesce(
                sqlfunc.sum(
                    sqlfunc.extract('epoch',
                        sqlfunc.coalesce(TimeLog.ended_at, now_utc) - TimeLog.started_at)
                ), 0
            ).label('secs')
        )
        .filter(TimeLog.started_at >= start)
        .group_by(TimeLog.user_id)
        .order_by(sqlfunc.text('secs DESC'))
        .limit(5).all()
    )
    user_ids = [r.user_id for r in worker_rows]
    users_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
    top_workers = [
        {
            'user': _user(users_map.get(r.user_id)),
            'seconds': int(r.secs),
        }
        for r in worker_rows if users_map.get(r.user_id)
    ]

    return _ok({
        'period': period,
        'by_status': by_status,
        'total': total,
        'by_type': by_type,
        'total_seconds': total_seconds,
        'my_seconds': my_seconds,
        'top_workers': top_workers,
    })


# ── Media Plan ────────────────────────────────────────────────────────────────

@api_v1_bp.get('/media-plan')
@jwt_required()
def media_plan():
    """
    Медиаплан — публикационные задачи, сгруппированные по дате.
    Query: month=YYYY-MM (default: текущий месяц)
    """
    from datetime import date, timedelta
    month_str = request.args.get('month', datetime.utcnow().strftime('%Y-%m'))
    try:
        year, month = map(int, month_str.split('-'))
        month_start = date(year, month, 1)
    except (ValueError, AttributeError):
        return _err('Неверный формат month (YYYY-MM)')

    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    # Задачи публикационного типа (placement, publication)
    all_pubs = Task.query.filter(
        Task.task_type.in_(['placement', 'publication']),
        Task.is_archived == False,
    ).all()

    by_day = {}
    no_date = []

    for t in all_pubs:
        raw = (t.dynamic_fields or {}).get('pub_date', '')
        pub_dt = None
        if raw:
            try:
                pub_dt = datetime.fromisoformat(raw)
            except Exception:
                pass

        if pub_dt and month_start <= pub_dt.date() < month_end:
            day = pub_dt.day
            by_day.setdefault(day, []).append({
                'id': t.id,
                'title': t.title,
                'status': t.status,
                'task_type': t.task_type,
                'pub_time': pub_dt.strftime('%H:%M'),
                'department': {'id': t.department.id, 'name': t.department.name} if t.department else None,
                'dynamic_fields': t.dynamic_fields or {},
            })
        elif not pub_dt:
            no_date.append({
                'id': t.id,
                'title': t.title,
                'status': t.status,
                'task_type': t.task_type,
                'department': {'id': t.department.id, 'name': t.department.name} if t.department else None,
            })

    # Sort items within each day by time
    for day_items in by_day.values():
        day_items.sort(key=lambda x: x['pub_time'])

    return _ok({
        'month': month_str,
        'year': year,
        'month_num': month,
        'by_day': {str(k): v for k, v in sorted(by_day.items())},
        'no_date': no_date,
    })


# ── Tags ──────────────────────────────────────────────────────────────────────

@api_v1_bp.get('/tags')
@jwt_required()
def get_tags():
    """Предопределённые теги."""
    return _ok([
        {'slug': t, 'label': t}
        for t in TaskTag.ALL
    ])


# ── Swagger UI ────────────────────────────────────────────────────────────────

_SWAGGER_HTML = '''<!DOCTYPE html>
<html>
<head>
  <title>Groove Work API v1</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>body{margin:0}</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({
  url: '/api/v1/openapi.json',
  dom_id: '#swagger-ui',
  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
  layout: 'BaseLayout',
  persistAuthorization: true,
  tryItOutEnabled: true,
});
</script>
</body>
</html>'''


@api_v1_bp.get('/docs')
def swagger_ui():
    """Swagger UI (интерактивная документация)."""
    return _SWAGGER_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}


@api_v1_bp.get('/openapi.json')
def openapi_spec():
    """OpenAPI 3.0 spec (для Swagger UI и генераторов клиентов)."""
    host = request.host_url.rstrip('/')
    spec = {
        'openapi': '3.0.3',
        'info': {
            'title': 'Groove Work API',
            'version': '1.0.0',
            'description': 'REST API для Android-приложения Groove Work',
        },
        'servers': [{'url': host}],
        'components': {
            'securitySchemes': {
                'Bearer': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'JWT',
                    'description': 'Получить токен через POST /api/v1/auth/login',
                }
            },
            'schemas': {
                'User': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'username': {'type': 'string'},
                        'full_name': {'type': 'string'},
                        'role': {'type': 'string', 'enum': ['super_admin', 'admin', 'manager', 'staff', 'tv']},
                        'is_active': {'type': 'boolean'},
                    },
                },
                'Task': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'title': {'type': 'string'},
                        'status': {'type': 'string', 'enum': ['new', 'in_progress', 'paused', 'done']},
                        'urgency': {'type': 'string', 'enum': ['slow', 'normal', 'important', 'urgent']},
                        'task_type': {'type': 'string'},
                        'tags': {'type': 'array', 'items': {'type': 'string'}},
                        'deadline': {'type': 'string', 'format': 'date-time', 'nullable': True},
                        'is_archived': {'type': 'boolean'},
                        'is_external': {'type': 'boolean'},
                        'is_overdue': {'type': 'boolean'},
                        'parent_task_id': {'type': 'integer', 'nullable': True},
                        'total_seconds': {'type': 'integer'},
                        'created_at': {'type': 'string', 'format': 'date-time'},
                        'updated_at': {'type': 'string', 'format': 'date-time'},
                        'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True},
                        'department': {
                            'nullable': True,
                            'type': 'object',
                            'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}},
                        },
                        'created_by': {'$ref': '#/components/schemas/User', 'nullable': True},
                        'assigned_to': {'$ref': '#/components/schemas/User', 'nullable': True},
                    },
                },
                'TaskDetail': {
                    'allOf': [
                        {'$ref': '#/components/schemas/Task'},
                        {
                            'type': 'object',
                            'properties': {
                                'description': {'type': 'string', 'nullable': True},
                                'customer_name': {'type': 'string', 'nullable': True},
                                'customer_phone': {'type': 'string', 'nullable': True},
                                'customer_email': {'type': 'string', 'nullable': True},
                                'dynamic_fields': {'type': 'object'},
                                'attachments': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'id': {'type': 'integer'},
                                            'original_name': {'type': 'string'},
                                            'download_url': {'type': 'string'},
                                            'yadisk_url': {'type': 'string', 'nullable': True},
                                            'uploaded_at': {'type': 'string'},
                                        },
                                    },
                                },
                                'comments': {
                                    'type': 'array',
                                    'items': {'$ref': '#/components/schemas/Comment'},
                                },
                            },
                        },
                    ]
                },
                'Comment': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'text': {'type': 'string'},
                        'created_at': {'type': 'string'},
                        'user': {'$ref': '#/components/schemas/User'},
                        'attachments': {'type': 'array', 'items': {'type': 'object'}},
                    },
                },
                'Paginated': {
                    'type': 'object',
                    'properties': {
                        'data': {'type': 'array', 'items': {}},
                        'meta': {
                            'type': 'object',
                            'properties': {
                                'page': {'type': 'integer'},
                                'per_page': {'type': 'integer'},
                                'total': {'type': 'integer'},
                                'pages': {'type': 'integer'},
                            },
                        },
                    },
                },
                'Error': {
                    'type': 'object',
                    'properties': {'error': {'type': 'string'}},
                },
            },
        },
        'security': [{'Bearer': []}],
        'paths': {
            '/api/v1/auth/login': {
                'post': {
                    'tags': ['auth'], 'summary': 'Авторизация', 'security': [],
                    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                        'type': 'object', 'required': ['username', 'password'],
                        'properties': {
                            'username': {'type': 'string', 'example': 'admin'},
                            'password': {'type': 'string', 'example': 'admin123'},
                        },
                    }}}},
                    'responses': {
                        '200': {'description': 'access_token + refresh_token + user'},
                        '400': {'description': 'Отсутствуют поля', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}},
                        '401': {'description': 'Неверные данные'},
                    },
                }
            },
            '/api/v1/auth/refresh': {
                'post': {
                    'tags': ['auth'], 'summary': 'Обновить access-токен',
                    'description': 'Передать refresh_token в Authorization: Bearer <refresh_token>',
                    'responses': {'200': {'description': 'Новый access_token'}},
                }
            },
            '/api/v1/auth/me': {
                'get': {
                    'tags': ['auth'], 'summary': 'Текущий пользователь',
                    'responses': {'200': {'description': 'User object'}},
                }
            },
            '/api/v1/tasks': {
                'get': {
                    'tags': ['tasks'], 'summary': 'Список задач (с пагинацией)',
                    'parameters': [
                        {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'default': 1}},
                        {'name': 'per_page', 'in': 'query', 'schema': {'type': 'integer', 'default': 20}},
                        {'name': 'status', 'in': 'query', 'schema': {'type': 'string'}, 'description': 'Comma-separated: new,in_progress,paused,done'},
                        {'name': 'urgency', 'in': 'query', 'schema': {'type': 'string', 'enum': ['slow', 'normal', 'important', 'urgent']}},
                        {'name': 'department_id', 'in': 'query', 'schema': {'type': 'integer'}},
                        {'name': 'assigned_to_id', 'in': 'query', 'schema': {'type': 'string'}, 'description': 'Integer или "me"'},
                        {'name': 'task_type', 'in': 'query', 'schema': {'type': 'string'}},
                        {'name': 'is_archived', 'in': 'query', 'schema': {'type': 'boolean', 'default': False}},
                        {'name': 'search', 'in': 'query', 'schema': {'type': 'string'}},
                    ],
                    'responses': {'200': {'description': 'Paginated tasks'}},
                },
                'post': {
                    'tags': ['tasks'], 'summary': 'Создать задачу',
                    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                        'type': 'object', 'required': ['title', 'task_type'],
                        'properties': {
                            'title': {'type': 'string'},
                            'task_type': {'type': 'string'},
                            'description': {'type': 'string'},
                            'urgency': {'type': 'string', 'enum': ['slow', 'normal', 'important', 'urgent'], 'default': 'normal'},
                            'deadline': {'type': 'string', 'format': 'date-time'},
                            'department_id': {'type': 'integer'},
                            'tags': {'type': 'array', 'items': {'type': 'string'}},
                            'customer_name': {'type': 'string'},
                            'customer_phone': {'type': 'string'},
                            'customer_email': {'type': 'string'},
                            'parent_task_id': {'type': 'integer'},
                            'dynamic_fields': {'type': 'object'},
                        },
                    }}}},
                    'responses': {
                        '201': {'description': 'Созданная задача (TaskDetail)'},
                        '400': {'description': 'Ошибка валидации'},
                    },
                },
            },
            '/api/v1/tasks/{task_id}': {
                'parameters': [{'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                'get': {
                    'tags': ['tasks'], 'summary': 'Задача с комментариями и вложениями',
                    'responses': {'200': {'description': 'TaskDetail'}, '404': {'description': 'Не найдена'}},
                },
                'patch': {
                    'tags': ['tasks'], 'summary': 'Обновить задачу (partial)',
                    'requestBody': {'content': {'application/json': {'schema': {'type': 'object'}}}},
                    'responses': {'200': {'description': 'Обновлённая задача'}, '403': {'description': 'Нет прав'}},
                },
                'delete': {
                    'tags': ['tasks'], 'summary': 'Удалить задачу (admin+)',
                    'responses': {'200': {'description': 'OK'}, '403': {'description': 'Нет прав'}},
                },
            },
            '/api/v1/tasks/{task_id}/done': {
                'parameters': [{'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                'post': {
                    'tags': ['tasks'], 'summary': 'Завершить задачу',
                    'responses': {'200': {'description': 'OK'}, '400': {'description': 'Есть подзадачи / нет типа'}},
                },
            },
            '/api/v1/tasks/{task_id}/timer/start': {
                'parameters': [{'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                'post': {
                    'tags': ['timer'], 'summary': 'Запустить таймер',
                    'requestBody': {'content': {'application/json': {'schema': {
                        'type': 'object',
                        'properties': {'force': {'type': 'boolean', 'description': 'Остановить текущий и переключиться'}},
                    }}}},
                    'responses': {
                        '200': {'description': '{started} / {conflict: taken|busy} / {already_running}'},
                        '400': {'description': 'Задача в архиве / нет типа'},
                    },
                },
            },
            '/api/v1/tasks/{task_id}/timer/pause': {
                'parameters': [{'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                'post': {
                    'tags': ['timer'], 'summary': 'Пауза таймера',
                    'responses': {'200': {'description': '{paused, task_status}'}, '400': {'description': 'Таймер не запущен'}},
                },
            },
            '/api/v1/tasks/my-timer': {
                'get': {
                    'tags': ['timer'], 'summary': 'Мой активный таймер',
                    'responses': {'200': {'description': '{active, task_id?, started_at?}'}},
                },
            },
            '/api/v1/tasks/{task_id}/comments': {
                'parameters': [{'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}],
                'get': {
                    'tags': ['comments'], 'summary': 'Комментарии задачи',
                    'responses': {'200': {'description': 'Список комментариев'}},
                },
                'post': {
                    'tags': ['comments'], 'summary': 'Добавить комментарий',
                    'requestBody': {'required': True, 'content': {'application/json': {'schema': {
                        'type': 'object', 'required': ['text'],
                        'properties': {'text': {'type': 'string'}},
                    }}}},
                    'responses': {'201': {'description': 'Comment'}, '400': {'description': 'Нет текста'}},
                },
            },
            '/api/v1/tasks/{task_id}/comments/{comment_id}': {
                'parameters': [
                    {'name': 'task_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                    {'name': 'comment_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                ],
                'delete': {
                    'tags': ['comments'], 'summary': 'Удалить комментарий',
                    'responses': {'200': {'description': 'OK'}, '403': {'description': 'Нет прав'}},
                },
            },
            '/api/v1/task-types': {
                'get': {'tags': ['lookups'], 'summary': 'Типы задач', 'responses': {'200': {'description': '[{slug, label}]'}}},
            },
            '/api/v1/departments': {
                'get': {'tags': ['lookups'], 'summary': 'Подразделения', 'responses': {'200': {'description': '[{id, name, head}]'}}},
            },
            '/api/v1/users': {
                'get': {'tags': ['lookups'], 'summary': 'Активные пользователи', 'responses': {'200': {'description': '[User]'}}},
            },
        },
    }
    return jsonify(spec)
