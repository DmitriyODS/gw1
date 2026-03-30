import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from extensions import db
from models import TaskType, Department

lists_bp = Blueprint('lists', __name__, url_prefix='/lists')


@lists_bp.route('/')
@login_required
def index():
    if not current_user.can_manage:
        flash('Недостаточно прав', 'danger')
        return redirect(url_for('tasks.list_tasks'))
    list_type = request.args.get('list', 'task_types')
    task_types = TaskType.query.order_by(TaskType.label).all()
    departments = Department.query.order_by(Department.name).all()
    return render_template('lists/index.html', list_type=list_type,
                           task_types=task_types, departments=departments)


# ── Task types CRUD ──

@lists_bp.route('/task-types', methods=['POST'])
@login_required
def create_task_type():
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    data = request.get_json() or {}
    slug = data.get('slug', '').strip().lower().replace(' ', '_')
    label = data.get('label', '').strip()
    if not slug or not label:
        return jsonify({'error': 'Укажите slug и название'}), 400
    if TaskType.query.filter_by(slug=slug).first():
        return jsonify({'error': 'Тип с таким slug уже существует'}), 400
    try:
        coefficient = float(data.get('coefficient', 1.0))
        if coefficient <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'Коэффициент должен быть положительным числом'}), 400
    max_order = db.session.query(db.func.max(TaskType.sort_order)).scalar() or 0
    tt = TaskType(slug=slug, label=label, sort_order=max_order + 1, coefficient=coefficient)
    db.session.add(tt)
    db.session.commit()
    return jsonify({'ok': True, 'id': tt.id, 'slug': tt.slug, 'label': tt.label, 'coefficient': tt.coefficient})


@lists_bp.route('/task-types/<int:tt_id>', methods=['PUT'])
@login_required
def update_task_type(tt_id):
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    tt = TaskType.query.get_or_404(tt_id)
    data = request.get_json() or {}
    label = data.get('label', '').strip()
    if not label:
        return jsonify({'error': 'Укажите название'}), 400
    tt.label = label
    if 'coefficient' in data:
        try:
            coefficient = float(data['coefficient'])
            if coefficient <= 0:
                raise ValueError
            tt.coefficient = coefficient
        except (TypeError, ValueError):
            return jsonify({'error': 'Коэффициент должен быть положительным числом'}), 400
    db.session.commit()
    return jsonify({'ok': True})


@lists_bp.route('/task-types/<int:tt_id>', methods=['DELETE'])
@login_required
def delete_task_type(tt_id):
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    tt = TaskType.query.get_or_404(tt_id)
    db.session.delete(tt)
    db.session.commit()
    return jsonify({'ok': True})


# ── Departments CRUD ──

@lists_bp.route('/departments', methods=['POST'])
@login_required
def create_department():
    if not current_user.can_manage:
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
    if not current_user.can_manage:
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
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    return jsonify({'ok': True})


# ── Export / Import ──

@lists_bp.route('/task-types/export', methods=['GET'])
@login_required
def export_task_types():
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    types = TaskType.query.order_by(TaskType.label).all()
    data = [{'slug': t.slug, 'label': t.label, 'sort_order': t.sort_order, 'coefficient': t.coefficient} for t in types]
    return Response(
        json.dumps({'task_types': data}, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="task_types.json"'}
    )


@lists_bp.route('/task-types/import', methods=['POST'])
@login_required
def import_task_types():
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Файл не передан'}), 400
    try:
        data = json.loads(file.read().decode('utf-8'))
        items = data.get('task_types', data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return jsonify({'error': 'Неверный формат: ожидается список task_types'}), 400
    except Exception:
        return jsonify({'error': 'Неверный JSON'}), 400

    added = 0
    for item in items:
        slug = str(item.get('slug', '')).strip().lower().replace(' ', '_')
        label = str(item.get('label', '')).strip()
        if not slug or not label:
            continue
        if TaskType.query.filter_by(slug=slug).first():
            continue
        max_order = db.session.query(db.func.max(TaskType.sort_order)).scalar() or 0
        try:
            coef = float(item.get('coefficient', 1.0))
            coef = coef if coef > 0 else 1.0
        except (TypeError, ValueError):
            coef = 1.0
        db.session.add(TaskType(slug=slug, label=label, sort_order=item.get('sort_order', max_order + 1), coefficient=coef))
        added += 1
    db.session.commit()
    return jsonify({'ok': True, 'added': added})


@lists_bp.route('/departments/export', methods=['GET'])
@login_required
def export_departments():
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    depts = Department.query.order_by(Department.name).all()
    data = [{'name': d.name, 'head': d.head} for d in depts]
    return Response(
        json.dumps({'departments': data}, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="departments.json"'}
    )


@lists_bp.route('/departments/import', methods=['POST'])
@login_required
def import_departments():
    if not current_user.can_manage:
        return jsonify({'error': 'Нет прав'}), 403
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Файл не передан'}), 400
    try:
        data = json.loads(file.read().decode('utf-8'))
        items = data.get('departments', data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return jsonify({'error': 'Неверный формат: ожидается список departments'}), 400
    except Exception:
        return jsonify({'error': 'Неверный JSON'}), 400

    added = 0
    for item in items:
        name = str(item.get('name', '')).strip()
        head = str(item.get('head', '')).strip()
        if not name:
            continue
        if Department.query.filter_by(name=name).first():
            continue
        db.session.add(Department(name=name, head=head))
        added += 1
    db.session.commit()
    return jsonify({'ok': True, 'added': added})
