from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import User, Department, Role

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
