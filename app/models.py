from datetime import datetime
from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index


class Role:
    SUPER_ADMIN = 'super_admin'
    MANAGER = 'manager'
    ADMIN = 'admin'
    STAFF = 'staff'
    ALL = ['super_admin', 'manager', 'admin', 'staff']
    LABELS = {
        'super_admin': 'Super Admin',
        'manager': 'Руководитель',
        'admin': 'Администратор',
        'staff': 'Сотрудник',
    }


class TaskStatus:
    NEW = 'new'
    IN_PROGRESS = 'in_progress'
    PAUSED = 'paused'
    REVIEW = 'review'
    DONE = 'done'
    LABELS = {
        'new': 'Новая',
        'in_progress': 'В работе',
        'paused': 'На паузе',
        'review': 'Проверка',
        'done': 'Готово',
    }
    COLORS = {
        'new': 'neutral',
        'in_progress': 'primary',
        'paused': 'warning',
        'review': 'info',
        'done': 'success',
    }


class Urgency:
    SLOW = 'slow'
    NORMAL = 'normal'
    IMPORTANT = 'important'
    URGENT = 'urgent'
    ORDER = {'urgent': 4, 'important': 3, 'normal': 2, 'slow': 1}
    LABELS = {
        'slow': 'Неспешно',
        'normal': 'Обычно',
        'important': 'Важно',
        'urgent': 'Срочно',
    }
    COLORS = {
        'slow': 'neutral',
        'normal': 'info',
        'important': 'warning',
        'urgent': 'error',
    }


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.STAFF)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def can_manage(self):
        return self.role in (Role.SUPER_ADMIN, Role.MANAGER)

    @property
    def can_admin(self):
        return self.role in (Role.SUPER_ADMIN, Role.MANAGER, Role.ADMIN)

    @property
    def active_timer(self):
        return TimeLog.query.filter_by(user_id=self.id, ended_at=None).first()


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)


class Task(db.Model):
    __tablename__ = 'tasks'
    __table_args__ = (
        Index('ix_tasks_status', 'status'),
        Index('ix_tasks_archived', 'is_archived'),
        Index('ix_tasks_urgency', 'urgency'),
        Index('ix_tasks_deadline', 'deadline'),
    )
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(50))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    task_type = db.Column(db.String(50))
    urgency = db.Column(db.String(20), default=Urgency.NORMAL)
    status = db.Column(db.String(20), default=TaskStatus.NEW)
    deadline = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    dynamic_fields = db.Column(db.JSON, default=dict)
    is_archived = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship('Department', backref='tasks')
    created_by = db.relationship('User', backref='created_tasks', foreign_keys=[created_by_id])
    attachments = db.relationship('TaskAttachment', backref='task', lazy='dynamic')
    time_logs = db.relationship('TimeLog', backref='task', lazy='dynamic')

    @property
    def total_seconds(self):
        total = 0
        for log in self.time_logs:
            end = log.ended_at or datetime.utcnow()
            total += (end - log.started_at).total_seconds()
        return int(total)

    @property
    def is_overdue(self):
        return (self.deadline and
                self.deadline < datetime.utcnow() and
                self.status != TaskStatus.DONE)

    @property
    def urgency_order(self):
        return Urgency.ORDER.get(self.urgency, 2)

    @property
    def active_timers(self):
        return self.time_logs.filter_by(ended_at=None).all()


class TaskAttachment(db.Model):
    __tablename__ = 'task_attachments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    filename = db.Column(db.String(255))
    original_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class TimeLog(db.Model):
    __tablename__ = 'time_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='time_logs')

    @property
    def duration_seconds(self):
        end = self.ended_at or datetime.utcnow()
        return int((end - self.started_at).total_seconds())


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
