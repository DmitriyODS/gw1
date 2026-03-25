import io
import json
import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_login import login_required, current_user
from extensions import db
from models import User, Department, Role, Task, TaskAttachment, TaskComment, CommentAttachment, TimeLog, TaskStatus, TaskType, Rhythm, PlanGroup, Plan

_LOGIN_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_\-]{3,}$')


def _validate_user_fields(username, password, is_new):
    """Returns error message or None."""
    if not _LOGIN_RE.match(username):
        return 'Логин: минимум 4 символа, должен начинаться с буквы, допустимы буквы, цифры, _ и -'
    if is_new and len(password) < 6:
        return 'Пароль должен содержать минимум 6 символов'
    if not is_new and password and len(password) < 6:
        return 'Пароль должен содержать минимум 6 символов'
    return None


def _allowed_roles_for(creator):
    """Returns set of role values that creator is allowed to assign."""
    if creator.is_super_admin:
        return {Role.SUPER_ADMIN, Role.ADMIN, Role.MANAGER, Role.STAFF, Role.TV}
    if creator.can_manage:  # admin
        return {Role.MANAGER, Role.STAFF, Role.TV}
    return set()

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _reset_sequences():
    """Reset PostgreSQL sequences to max(id) for all tables after bulk import."""
    tables = ['users', 'departments', 'task_types', 'tasks', 'task_attachments',
              'task_comments', 'comment_attachments', 'time_logs',
              'rhythms', 'plan_groups', 'plans']
    with db.engine.connect() as conn:
        for table in tables:
            conn.execute(db.text(
                f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 1))"
            ))
        conn.commit()


@admin_bp.route('/users')
@login_required
def users():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, Role=Role)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.users'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        new_role = request.form.get('role', Role.STAFF)
        err = _validate_user_fields(username, password, is_new=True)
        if err:
            flash(err, 'danger')
            return redirect(url_for('admin.create_user'))
        allowed = _allowed_roles_for(current_user)
        if new_role not in allowed:
            flash('Недостаточно прав для назначения этой роли', 'danger')
            return redirect(url_for('admin.create_user'))
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'danger')
        else:
            user = User(
                username=username,
                email=request.form['email'].strip(),
                full_name=request.form['full_name'].strip(),
                role=new_role,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Пользователь создан', 'success')
            return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', user=None, Role=Role)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.users'))
    user = User.query.get_or_404(user_id)
    if user.is_super_admin and not current_user.is_super_admin:
        flash('Нельзя редактировать Super Admin', 'danger')
        return redirect(url_for('admin.users'))
    # Admin can only edit users whose role is within their allowed set (except editing self)
    if not current_user.is_super_admin and user.id != current_user.id:
        if user.role not in _allowed_roles_for(current_user):
            flash('Недостаточно прав для редактирования этого пользователя', 'danger')
            return redirect(url_for('admin.users'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        new_role = request.form.get('role', user.role)
        err = _validate_user_fields(username, password, is_new=False)
        if err:
            flash(err, 'danger')
            return redirect(url_for('admin.edit_user', user_id=user_id))
        allowed = _allowed_roles_for(current_user)
        if new_role not in allowed and not user.is_super_admin:
            flash('Недостаточно прав для назначения этой роли', 'danger')
            return redirect(url_for('admin.edit_user', user_id=user_id))
        user.username = username
        user.email = request.form['email'].strip()
        user.full_name = request.form['full_name'].strip()
        if not user.is_super_admin:
            user.role = new_role
        # Prevent deactivating yourself
        if user.id != current_user.id:
            user.is_active = 'is_active' in request.form
        if password:
            user.set_password(password)
        db.session.commit()
        flash('Пользователь обновлён', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', user=user, Role=Role)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.users'))
    user = User.query.get_or_404(user_id)
    if user.is_super_admin:
        flash('Нельзя удалить Super Admin', 'danger')
        return redirect(url_for('admin.users'))
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/departments', methods=['GET', 'POST'])
@login_required
def departments():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        head = request.form.get('head', '').strip()
        if name and not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name, head=head))
            db.session.commit()
            flash('Отдел добавлен', 'success')
        elif name:
            flash('Такой отдел уже существует', 'warning')
    all_depts = Department.query.order_by(Department.name).all()
    return render_template('admin/departments.html', departments=all_depts)


@admin_bp.route('/departments/<int:dept_id>/delete', methods=['POST'])
@login_required
def delete_department(dept_id):
    if not current_user.is_super_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.departments'))
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    flash('Отдел удалён', 'success')
    return redirect(url_for('admin.departments'))


def _dt(d):
    return d.isoformat() if d else None


def build_backup():
    return {
        'exported_at': datetime.utcnow().isoformat(),
        'version': '2',
        'task_types': [
            {'id': tt.id, 'slug': tt.slug, 'label': tt.label, 'sort_order': tt.sort_order}
            for tt in TaskType.query.order_by(TaskType.sort_order, TaskType.id).all()
        ],
        'departments': [
            {'id': d.id, 'name': d.name, 'head': d.head}
            for d in Department.query.order_by(Department.id).all()
        ],
        'users': [
            {
                'id': u.id, 'username': u.username, 'email': u.email,
                'password_hash': u.password_hash, 'full_name': u.full_name,
                'role': u.role, 'is_active': u.is_active,
                'created_at': _dt(u.created_at),
            }
            for u in User.query.order_by(User.id).all()
        ],
        'tasks': [
            {
                'id': t.id, 'title': t.title, 'description': t.description,
                'customer_name': t.customer_name, 'customer_phone': t.customer_phone,
                'department_id': t.department_id, 'task_type': t.task_type,
                'urgency': t.urgency, 'status': t.status,
                'deadline': _dt(t.deadline), 'created_by_id': t.created_by_id,
                'dynamic_fields': t.dynamic_fields, 'is_archived': t.is_archived,
                'archived_at': _dt(t.archived_at), 'completed_at': _dt(t.completed_at),
                'created_at': _dt(t.created_at),
            }
            for t in Task.query.order_by(Task.id).all()
        ],
        'attachments': [
            {
                'id': a.id, 'task_id': a.task_id,
                'filename': a.filename, 'original_name': a.original_name,
                'uploaded_at': _dt(a.uploaded_at),
            }
            for a in TaskAttachment.query.order_by(TaskAttachment.id).all()
        ],
        'comments': [
            {
                'id': c.id, 'task_id': c.task_id, 'user_id': c.user_id,
                'text': c.text, 'filename': c.filename, 'original_name': c.original_name,
                'created_at': _dt(c.created_at),
            }
            for c in TaskComment.query.order_by(TaskComment.id).all()
        ],
        'comment_attachments': [
            {
                'id': a.id, 'comment_id': a.comment_id,
                'filename': a.filename, 'original_name': a.original_name,
                'uploaded_at': _dt(a.uploaded_at),
            }
            for a in CommentAttachment.query.order_by(CommentAttachment.id).all()
        ],
        'time_logs': [
            {
                'id': l.id, 'task_id': l.task_id, 'user_id': l.user_id,
                'started_at': _dt(l.started_at), 'ended_at': _dt(l.ended_at),
            }
            for l in TimeLog.query.order_by(TimeLog.id).all()
        ],
        'rhythms': [
            {
                'id': r.id, 'name': r.name, 'description': r.description,
                'frequency': r.frequency, 'day_of_week': r.day_of_week,
                'day_of_month': r.day_of_month, 'trigger_time': r.trigger_time,
                'task_title': r.task_title, 'task_description': r.task_description,
                'task_tags': r.task_tags, 'task_urgency': r.task_urgency,
                'task_type': r.task_type, 'department_id': r.department_id,
                'is_active': r.is_active, 'last_run_at': _dt(r.last_run_at),
                'created_at': _dt(r.created_at), 'created_by_id': r.created_by_id,
            }
            for r in Rhythm.query.order_by(Rhythm.id).all()
        ],
        'plan_groups': [
            {
                'id': pg.id, 'name': pg.name,
                'created_at': _dt(pg.created_at), 'created_by_id': pg.created_by_id,
            }
            for pg in PlanGroup.query.order_by(PlanGroup.id).all()
        ],
        'plans': [
            {
                'id': p.id, 'title': p.title, 'description': p.description,
                'customer_name': p.customer_name, 'customer_phone': p.customer_phone,
                'customer_email': p.customer_email, 'department_id': p.department_id,
                'task_type': p.task_type, 'urgency': p.urgency,
                'tags': p.tags, 'dynamic_fields': p.dynamic_fields,
                'group_id': p.group_id, 'release_date': _dt(p.release_date),
                'is_converted': p.is_converted, 'converted_task_id': p.converted_task_id,
                'created_by_id': p.created_by_id, 'created_at': _dt(p.created_at),
            }
            for p in Plan.query.order_by(Plan.id).all()
        ],
    }


@admin_bp.route('/archive')
@login_required
def archive():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    stats = {
        'users': User.query.count(),
        'tasks': Task.query.count(),
        'comments': TaskComment.query.count(),
        'time_logs': TimeLog.query.count(),
        'attachments': TaskAttachment.query.count(),
        'departments': Department.query.count(),
    }
    review_count = Task.query.filter_by(status='review').count()
    return render_template('admin/archive.html', stats=stats, review_task_count=review_count)


@admin_bp.route('/archive/migrate-review', methods=['POST'])
@login_required
def migrate_review():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.archive'))
    now = datetime.utcnow()
    # Задачи без completed_at — ставим статус и дату закрытия
    c1 = Task.query.filter(Task.status == 'review', Task.completed_at.is_(None)).update(
        {'status': TaskStatus.DONE, 'completed_at': now}, synchronize_session=False
    )
    # Задачи с completed_at — только статус
    c2 = Task.query.filter(Task.status == 'review', Task.completed_at.isnot(None)).update(
        {'status': TaskStatus.DONE}, synchronize_session=False
    )
    db.session.commit()
    flash(f'Переведено в «Готово»: {c1 + c2} задач', 'success')
    return redirect(url_for('admin.archive'))


@admin_bp.route('/archive/export')
@login_required
def archive_export():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    data = build_backup()
    blob = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    fname = f"groove_work_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return send_file(
        io.BytesIO(blob),
        mimetype='application/json',
        as_attachment=True,
        download_name=fname,
    )


@admin_bp.route('/archive/preview')
@login_required
def archive_preview():
    if not current_user.can_manage:
        return jsonify({'error': 'forbidden'}), 403
    data = build_backup()
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
    )


@admin_bp.route('/archive/import', methods=['POST'])
@login_required
def archive_import():
    if not current_user.is_super_admin:
        flash('Только Super Admin может импортировать данные', 'danger')
        return redirect(url_for('admin.archive'))

    f = request.files.get('backup_file')
    if not f or not f.filename.endswith('.json'):
        flash('Выберите JSON-файл', 'danger')
        return redirect(url_for('admin.archive'))

    try:
        data = json.loads(f.read().decode('utf-8'))
    except Exception:
        flash('Не удалось разобрать JSON', 'danger')
        return redirect(url_for('admin.archive'))

    try:
        # Clear existing data (order matters for FK)
        TimeLog.query.delete()
        CommentAttachment.query.delete()
        TaskComment.query.delete()
        TaskAttachment.query.delete()
        Plan.query.delete()
        PlanGroup.query.delete()
        Rhythm.query.delete()
        # Nullify self-referential FK before deleting tasks
        db.session.execute(db.text("UPDATE tasks SET parent_task_id = NULL"))
        Task.query.delete()
        User.query.delete()
        Department.query.delete()
        TaskType.query.delete()
        db.session.flush()

        def parse_dt(s):
            return datetime.fromisoformat(s) if s else None

        # Batch-вставки вместо поштучных db.session.add() — в разы быстрее при больших объёмах
        db.session.bulk_insert_mappings(TaskType, [
            {'id': tt['id'], 'slug': tt['slug'], 'label': tt['label'], 'sort_order': tt.get('sort_order', 0)}
            for tt in data.get('task_types', [])
        ])
        db.session.bulk_insert_mappings(Department, [
            {'id': d['id'], 'name': d['name'], 'head': d.get('head', '')}
            for d in data.get('departments', [])
        ])
        db.session.flush()

        db.session.bulk_insert_mappings(User, [
            {
                'id': u['id'], 'username': u['username'], 'email': u['email'],
                'password_hash': u['password_hash'], 'full_name': u['full_name'],
                'role': u['role'], 'is_active': u.get('is_active', True),
                'created_at': parse_dt(u.get('created_at')),
            }
            for u in data.get('users', [])
        ])
        db.session.flush()

        # Insert tasks without parent_task_id first (self-referential FK)
        db.session.bulk_insert_mappings(Task, [
            {
                'id': t['id'], 'title': t['title'], 'description': t.get('description'),
                'customer_name': t.get('customer_name'), 'customer_phone': t.get('customer_phone'),
                'customer_email': t.get('customer_email'),
                'department_id': t.get('department_id'), 'task_type': t.get('task_type'),
                'urgency': t.get('urgency', 'normal'), 'status': t.get('status', 'new'),
                'deadline': parse_dt(t.get('deadline')), 'created_by_id': t.get('created_by_id'),
                'assigned_to_id': t.get('assigned_to_id'),
                'parent_task_id': None,
                'tags': t.get('tags') or [],
                'dynamic_fields': t.get('dynamic_fields') or {},
                'is_archived': t.get('is_archived', False),
                'archived_at': parse_dt(t.get('archived_at')),
                'completed_at': parse_dt(t.get('completed_at')),
                'created_at': parse_dt(t.get('created_at')),
                'updated_at': parse_dt(t.get('updated_at')),
            }
            for t in data.get('tasks', [])
        ])
        db.session.flush()
        # Second pass: restore parent_task_id
        for t in data.get('tasks', []):
            if t.get('parent_task_id'):
                db.session.execute(
                    db.text("UPDATE tasks SET parent_task_id = :pid WHERE id = :id"),
                    {'pid': t['parent_task_id'], 'id': t['id']}
                )
        db.session.flush()

        db.session.bulk_insert_mappings(TaskAttachment, [
            {
                'id': a['id'], 'task_id': a['task_id'],
                'filename': a.get('filename'), 'original_name': a.get('original_name'),
                'uploaded_at': parse_dt(a.get('uploaded_at')),
            }
            for a in data.get('attachments', [])
        ])

        db.session.bulk_insert_mappings(TaskComment, [
            {
                'id': c['id'], 'task_id': c['task_id'], 'user_id': c['user_id'],
                'text': c.get('text'), 'filename': c.get('filename'),
                'original_name': c.get('original_name'),
                'created_at': parse_dt(c.get('created_at')),
            }
            for c in data.get('comments', [])
        ])

        db.session.bulk_insert_mappings(CommentAttachment, [
            {
                'id': a['id'], 'comment_id': a['comment_id'],
                'filename': a.get('filename'), 'original_name': a.get('original_name'),
                'uploaded_at': parse_dt(a.get('uploaded_at')),
            }
            for a in data.get('comment_attachments', [])
        ])

        db.session.bulk_insert_mappings(TimeLog, [
            {
                'id': l['id'], 'task_id': l['task_id'], 'user_id': l['user_id'],
                'started_at': parse_dt(l['started_at']),
                'ended_at': parse_dt(l.get('ended_at')),
            }
            for l in data.get('time_logs', [])
        ])

        db.session.bulk_insert_mappings(Rhythm, [
            {
                'id': r['id'], 'name': r['name'], 'description': r.get('description'),
                'frequency': r.get('frequency', 'daily'),
                'day_of_week': r.get('day_of_week'), 'day_of_month': r.get('day_of_month'),
                'trigger_time': r.get('trigger_time'),
                'task_title': r['task_title'], 'task_description': r.get('task_description'),
                'task_tags': r.get('task_tags') or [], 'task_urgency': r.get('task_urgency', 'normal'),
                'task_type': r.get('task_type'), 'department_id': r.get('department_id'),
                'is_active': r.get('is_active', True), 'last_run_at': parse_dt(r.get('last_run_at')),
                'created_at': parse_dt(r.get('created_at')), 'created_by_id': r.get('created_by_id'),
            }
            for r in data.get('rhythms', [])
        ])

        db.session.bulk_insert_mappings(PlanGroup, [
            {
                'id': pg['id'], 'name': pg['name'],
                'created_at': parse_dt(pg.get('created_at')),
                'created_by_id': pg.get('created_by_id'),
            }
            for pg in data.get('plan_groups', [])
        ])

        db.session.bulk_insert_mappings(Plan, [
            {
                'id': p['id'], 'title': p['title'], 'description': p.get('description'),
                'customer_name': p.get('customer_name'), 'customer_phone': p.get('customer_phone'),
                'customer_email': p.get('customer_email'), 'department_id': p.get('department_id'),
                'task_type': p.get('task_type'), 'urgency': p.get('urgency', 'normal'),
                'tags': p.get('tags') or [], 'dynamic_fields': p.get('dynamic_fields') or {},
                'group_id': p.get('group_id'), 'release_date': parse_dt(p.get('release_date')),
                'is_converted': p.get('is_converted', False),
                'converted_task_id': p.get('converted_task_id'),
                'created_by_id': p.get('created_by_id'), 'created_at': parse_dt(p.get('created_at')),
            }
            for p in data.get('plans', [])
        ])

        db.session.commit()
        # Reset sequences so new inserts don't collide with imported IDs
        _reset_sequences()
        counts = {k: len(data.get(k, [])) for k in ('users','tasks','comments','comment_attachments','time_logs','attachments','departments','task_types','rhythms','plan_groups','plans')}
        flash(
            f"Импорт завершён: {counts['task_types']} типов задач, {counts['departments']} подразд., "
            f"{counts['users']} польз., {counts['tasks']} задач, {counts['rhythms']} ритмов, "
            f"{counts['plans']} планов, {counts['comments']} комм., {counts['time_logs']} тайм-логов",
            'success'
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка импорта: {e}', 'danger')

    return redirect(url_for('admin.archive'))
