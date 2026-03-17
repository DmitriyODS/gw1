from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Plan, PlanGroup, Task, TaskStatus, TaskTag, Urgency, Department
from blueprints.public import TASK_TYPES, PUB_SUBTYPES, PLATFORMS, AUTO_TAGS

plans_bp = Blueprint('plans', __name__)


def convert_due_plans():
    """Convert plans whose release_date has passed into tasks. Returns count converted."""
    due = Plan.query.filter(
        Plan.release_date <= datetime.utcnow(),
        Plan.is_converted == False
    ).all()
    if not due:
        return 0
    for plan in due:
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
            created_by_id=plan.created_by_id,
        )
        db.session.add(task)
        db.session.flush()
        if plan.task_type == 'publication':
            db.session.add(Task(
                title=f'[Дизайн] {task.title}',
                task_type='publication', tags=[TaskTag.DESIGN],
                urgency=task.urgency, department_id=task.department_id,
                parent_task_id=task.id, status=TaskStatus.NEW,
                dynamic_fields={}, created_by_id=plan.created_by_id,
            ))
            db.session.add(Task(
                title=f'[Текст] {task.title}',
                task_type='publication', tags=[TaskTag.TEXT],
                urgency=task.urgency, department_id=task.department_id,
                parent_task_id=task.id, status=TaskStatus.NEW,
                dynamic_fields={}, created_by_id=plan.created_by_id,
            ))
        plan.is_converted = True
        plan.converted_task_id = task.id
    db.session.commit()
    return len(due)


@plans_bp.route('/plans')
@login_required
def index():
    converted = convert_due_plans()
    groups = PlanGroup.query.order_by(PlanGroup.name).all()
    group_id = request.args.get('group', type=int)

    q = Plan.query.filter_by(is_converted=False)
    if group_id:
        q = q.filter_by(group_id=group_id)
    plans = q.order_by(Plan.release_date.asc(), Plan.created_at.desc()).all()

    departments = Department.query.order_by(Department.name).all()
    # Group counts for filter bar
    total_count = Plan.query.filter_by(is_converted=False).count()
    group_counts = {
        g.id: Plan.query.filter_by(group_id=g.id, is_converted=False).count()
        for g in groups
    }
    return render_template('plans/index.html',
                           plans=plans, groups=groups,
                           active_group=group_id,
                           converted=converted,
                           departments=departments,
                           total_count=total_count,
                           group_counts=group_counts,
                           now=datetime.utcnow(),
                           TaskTag=TaskTag, Urgency=Urgency,
                           task_types=TASK_TYPES,
                           pub_subtypes=PUB_SUBTYPES,
                           platforms=PLATFORMS)


@plans_bp.route('/plans/create', methods=['POST'])
@login_required
def create():
    plan = _plan_from_form(request.form, created_by_id=current_user.id)
    db.session.add(plan)
    db.session.commit()
    flash('План добавлен', 'success')
    gid = request.form.get('redirect_group', '')
    return redirect(url_for('plans.index', group=gid) if gid else url_for('plans.index'))


@plans_bp.route('/plans/<int:plan_id>/edit', methods=['POST'])
@login_required
def edit(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    _plan_from_form(request.form, plan=plan)
    db.session.commit()
    flash('План обновлён', 'success')
    gid = request.form.get('redirect_group', '')
    return redirect(url_for('plans.index', group=gid) if gid else url_for('plans.index'))


@plans_bp.route('/plans/<int:plan_id>/push', methods=['POST'])
@login_required
def push_to_board(plan_id):
    """Immediately convert a plan to a task regardless of release_date."""
    plan = Plan.query.get_or_404(plan_id)
    if plan.is_converted:
        flash('Этот план уже превращён в задачу', 'warning')
        return redirect(url_for('plans.index'))

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
        created_by_id=plan.created_by_id,
    )
    db.session.add(task)
    db.session.flush()

    if plan.task_type == 'publication':
        db.session.add(Task(
            title=f'[Дизайн] {task.title}',
            task_type='publication', tags=[TaskTag.DESIGN],
            urgency=task.urgency, department_id=task.department_id,
            parent_task_id=task.id, status=TaskStatus.NEW,
            dynamic_fields={}, created_by_id=plan.created_by_id,
        ))
        db.session.add(Task(
            title=f'[Текст] {task.title}',
            task_type='publication', tags=[TaskTag.TEXT],
            urgency=task.urgency, department_id=task.department_id,
            parent_task_id=task.id, status=TaskStatus.NEW,
            dynamic_fields={}, created_by_id=plan.created_by_id,
        ))

    plan.is_converted = True
    plan.converted_task_id = task.id
    db.session.commit()
    flash(f'План «{plan.title}» добавлен на доску', 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))


@plans_bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@login_required
def delete(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    if not current_user.can_admin and plan.created_by_id != current_user.id:
        flash('Нет прав', 'danger')
        return redirect(url_for('plans.index'))
    db.session.delete(plan)
    db.session.commit()
    flash('План удалён', 'success')
    return redirect(url_for('plans.index'))


@plans_bp.route('/plans/groups/create', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Введите название группы', 'warning')
        return redirect(url_for('plans.index'))
    if PlanGroup.query.filter_by(name=name).first():
        flash('Группа с таким названием уже существует', 'warning')
        return redirect(url_for('plans.index'))
    g = PlanGroup(name=name, created_by_id=current_user.id)
    db.session.add(g)
    db.session.commit()
    flash(f'Группа «{name}» создана', 'success')
    return redirect(url_for('plans.index', group=g.id))


@plans_bp.route('/plans/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    if not current_user.can_admin:
        flash('Нет прав', 'danger')
        return redirect(url_for('plans.index'))
    g = PlanGroup.query.get_or_404(group_id)
    Plan.query.filter_by(group_id=group_id).update({'group_id': None})
    db.session.delete(g)
    db.session.commit()
    flash(f'Группа «{g.name}» удалена', 'success')
    return redirect(url_for('plans.index'))


def _plan_from_form(form, plan=None, created_by_id=None):
    if plan is None:
        plan = Plan(created_by_id=created_by_id)

    task_type = form.get('task_type') or None
    dynamic = {}
    if task_type == 'publication':
        dynamic['subtype'] = form.get('subtype')
        dynamic['platforms'] = form.getlist('platforms')
        pub_url = form.get('pub_url', '').strip()
        if pub_url:
            dynamic['pub_url'] = pub_url
    elif task_type == 'revision':
        revision_ref = form.get('revision_ref', '').strip()
        if revision_ref:
            dynamic['revision_ref'] = revision_ref
    else:
        clarification = form.get('clarification', '').strip()
        if clarification:
            dynamic['clarification'] = clarification

    release_date_str = form.get('release_date', '').strip()
    release_date = datetime.strptime(release_date_str, '%Y-%m-%dT%H:%M') if release_date_str else None

    tags = form.getlist('tags')
    if not tags and task_type:
        tags = list(AUTO_TAGS.get(task_type, []))

    plan.title = form.get('title', '').strip()
    plan.description = form.get('description', '').strip() or None
    plan.customer_name = form.get('customer_name', '').strip() or None
    plan.customer_phone = form.get('customer_phone', '').strip() or None
    plan.department_id = form.get('department_id') or None
    plan.task_type = task_type
    plan.urgency = form.get('urgency', Urgency.NORMAL)
    plan.tags = tags
    plan.dynamic_fields = dynamic
    plan.group_id = form.get('group_id') or None
    plan.release_date = release_date
    return plan
