from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import TaskType, Department

lists_bp = Blueprint('lists', __name__, url_prefix='/lists')


@lists_bp.route('/')
@login_required
def index():
    if not current_user.can_admin:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    list_type = request.args.get('list', 'task_types')
    task_types = TaskType.query.order_by(TaskType.sort_order, TaskType.label).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('lists/index.html', list_type=list_type,
                           task_types=task_types, departments=departments)


# ── Task types CRUD ──

@lists_bp.route('/task-types', methods=['POST'])
@login_required
def create_task_type():
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    data = request.get_json() or {}
    slug = data.get('slug', '').strip().lower().replace(' ', '_')
    label = data.get('label', '').strip()
    if not slug or not label:
        return jsonify({'error': 'Укажите slug и название'}), 400
    if TaskType.query.filter_by(slug=slug).first():
        return jsonify({'error': 'Тип с таким slug уже существует'}), 400
    max_order = db.session.query(db.func.max(TaskType.sort_order)).scalar() or 0
    tt = TaskType(slug=slug, label=label, sort_order=max_order + 1)
    db.session.add(tt)
    db.session.commit()
    return jsonify({'ok': True, 'id': tt.id, 'slug': tt.slug, 'label': tt.label})


@lists_bp.route('/task-types/<int:tt_id>', methods=['PUT'])
@login_required
def update_task_type(tt_id):
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    tt = TaskType.query.get_or_404(tt_id)
    data = request.get_json() or {}
    label = data.get('label', '').strip()
    if not label:
        return jsonify({'error': 'Укажите название'}), 400
    tt.label = label
    db.session.commit()
    return jsonify({'ok': True})


@lists_bp.route('/task-types/<int:tt_id>', methods=['DELETE'])
@login_required
def delete_task_type(tt_id):
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    tt = TaskType.query.get_or_404(tt_id)
    db.session.delete(tt)
    db.session.commit()
    return jsonify({'ok': True})


# ── Departments CRUD ──

@lists_bp.route('/departments', methods=['POST'])
@login_required
def create_department():
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    head = data.get('head', '').strip()
    if not name:
        return jsonify({'error': 'Укажите название'}), 400
    if Department.query.filter_by(name=name).first():
        return jsonify({'error': 'Подразделение с таким названием уже существует'}), 400
    dept = Department(name=name, head=head)
    db.session.add(dept)
    db.session.commit()
    return jsonify({'ok': True, 'id': dept.id, 'name': dept.name, 'head': dept.head})


@lists_bp.route('/departments/<int:dept_id>', methods=['PUT'])
@login_required
def update_department(dept_id):
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    dept = Department.query.get_or_404(dept_id)
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    head = data.get('head', '').strip()
    if not name:
        return jsonify({'error': 'Укажите название'}), 400
    if Department.query.filter(Department.name == name, Department.id != dept_id).first():
        return jsonify({'error': 'Подразделение с таким названием уже существует'}), 400
    dept.name = name
    dept.head = head
    db.session.commit()
    return jsonify({'ok': True})


@lists_bp.route('/departments/<int:dept_id>', methods=['DELETE'])
@login_required
def delete_department(dept_id):
    if not current_user.can_admin:
        return jsonify({'error': 'Нет прав'}), 403
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    return jsonify({'ok': True})
