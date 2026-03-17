import io
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, Response
from flask_login import login_required, current_user
from extensions import db
from models import User, Department, Role, Task, TaskAttachment, TaskComment, TimeLog

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/users')
@login_required
def users():
    if not current_user.can_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, Role=Role)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if not current_user.is_super_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.users'))
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Пользователь с таким логином уже существует', 'danger')
        else:
            user = User(
                username=request.form['username'].strip(),
                email=request.form['email'].strip(),
                full_name=request.form['full_name'].strip(),
                role=request.form['role'],
            )
            user.set_password(request.form['password'])
            db.session.add(user)
            db.session.commit()
            flash('Пользователь создан', 'success')
            return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', user=None, Role=Role)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_super_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('admin.users'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form['username'].strip()
        user.email = request.form['email'].strip()
        user.full_name = request.form['full_name'].strip()
        if not user.is_super_admin:
            user.role = request.form['role']
        user.is_active = 'is_active' in request.form
        if request.form.get('password'):
            user.set_password(request.form['password'])
        db.session.commit()
        flash('Пользователь обновлён', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', user=user, Role=Role)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_super_admin:
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
    if not current_user.can_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name and not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name))
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
        'version': '1',
        'departments': [
            {'id': d.id, 'name': d.name}
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
        'time_logs': [
            {
                'id': l.id, 'task_id': l.task_id, 'user_id': l.user_id,
                'started_at': _dt(l.started_at), 'ended_at': _dt(l.ended_at),
            }
            for l in TimeLog.query.order_by(TimeLog.id).all()
        ],
    }


@admin_bp.route('/archive')
@login_required
def archive():
    if not current_user.can_admin:
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
    return render_template('admin/archive.html', stats=stats)


@admin_bp.route('/archive/export')
@login_required
def archive_export():
    if not current_user.can_admin:
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
    if not current_user.can_admin:
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
        TaskComment.query.delete()
        TaskAttachment.query.delete()
        Task.query.delete()
        User.query.delete()
        Department.query.delete()
        db.session.flush()

        def parse_dt(s):
            return datetime.fromisoformat(s) if s else None

        for d in data.get('departments', []):
            db.session.add(Department(id=d['id'], name=d['name']))
        db.session.flush()

        for u in data.get('users', []):
            obj = User(
                id=u['id'], username=u['username'], email=u['email'],
                password_hash=u['password_hash'], full_name=u['full_name'],
                role=u['role'], is_active=u.get('is_active', True),
                created_at=parse_dt(u.get('created_at')),
            )
            db.session.add(obj)
        db.session.flush()

        for t in data.get('tasks', []):
            db.session.add(Task(
                id=t['id'], title=t['title'], description=t.get('description'),
                customer_name=t.get('customer_name'), customer_phone=t.get('customer_phone'),
                department_id=t.get('department_id'), task_type=t.get('task_type'),
                urgency=t.get('urgency', 'normal'), status=t.get('status', 'new'),
                deadline=parse_dt(t.get('deadline')), created_by_id=t.get('created_by_id'),
                dynamic_fields=t.get('dynamic_fields') or {},
                is_archived=t.get('is_archived', False),
                archived_at=parse_dt(t.get('archived_at')),
                completed_at=parse_dt(t.get('completed_at')),
                created_at=parse_dt(t.get('created_at')),
            ))
        db.session.flush()

        for a in data.get('attachments', []):
            db.session.add(TaskAttachment(
                id=a['id'], task_id=a['task_id'],
                filename=a.get('filename'), original_name=a.get('original_name'),
                uploaded_at=parse_dt(a.get('uploaded_at')),
            ))

        for c in data.get('comments', []):
            db.session.add(TaskComment(
                id=c['id'], task_id=c['task_id'], user_id=c['user_id'],
                text=c.get('text'), filename=c.get('filename'),
                original_name=c.get('original_name'),
                created_at=parse_dt(c.get('created_at')),
            ))

        for l in data.get('time_logs', []):
            db.session.add(TimeLog(
                id=l['id'], task_id=l['task_id'], user_id=l['user_id'],
                started_at=parse_dt(l['started_at']),
                ended_at=parse_dt(l.get('ended_at')),
            ))

        db.session.commit()
        counts = {k: len(data.get(k, [])) for k in ('users','tasks','comments','time_logs','attachments','departments')}
        flash(
            f"Импорт завершён: {counts['users']} польз., {counts['tasks']} задач, "
            f"{counts['comments']} комм., {counts['time_logs']} тайм-логов",
            'success'
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка импорта: {e}', 'danger')

    return redirect(url_for('admin.archive'))
