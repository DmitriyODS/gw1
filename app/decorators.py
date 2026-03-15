from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage:
            flash('Недостаточно прав', 'danger')
            return redirect(url_for('tasks.list_tasks'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_admin:
            flash('Недостаточно прав', 'danger')
            return redirect(url_for('tasks.list_tasks'))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash('Недостаточно прав', 'danger')
            return redirect(url_for('tasks.list_tasks'))
        return f(*args, **kwargs)
    return decorated
