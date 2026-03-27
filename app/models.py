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
    TV = 'tv'
    ALL = ['super_admin', 'manager', 'admin', 'staff', 'tv']
    LABELS = {
        'super_admin': 'Super Admin',
        'manager': 'Руководитель',
        'admin': 'Администратор',
        'staff': 'Сотрудник',
        'tv': 'ТВ-экран',
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
        'done': 'Готово',
    }
    COLORS = {
        'new': 'neutral',
        'in_progress': 'primary',
        'paused': 'warning',
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


class TaskTag:
    DESIGN = 'дизайн'
    TEXT = 'текст'
    PUBLICATION = 'публикация'
    PHOTO_VIDEO = 'фото/видео'
    INTERNAL = 'внутреннее'
    EXTERNAL = 'внешнее'
    ALL = ['дизайн', 'текст', 'публикация', 'фото/видео', 'внутреннее', 'внешнее']
    # CSS badge color suffix for each tag
    BADGE_CLASS = {
        'дизайн':     'badge-tag-design',
        'текст':      'badge-tag-text',
        'публикация': 'badge-tag-pub',
        'фото/видео': 'badge-tag-photo',
        'внутреннее': 'badge-tag-internal',
        'внешнее':    'badge-tag-external',
    }


class RhythmFrequency:
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    LABELS = {
        'daily': 'Ежедневно',
        'weekly': 'Еженедельно',
        'monthly': 'Ежемесячно',
    }
    WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


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
    mail_user     = db.Column(db.String(200), nullable=True)
    mail_password = db.Column(db.String(200), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def can_manage(self):
        """System management: users, lists, settings (admin+)."""
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN)

    @property
    def can_admin(self):
        """Task management: delete tasks, admin-pause, delegate (manager+)."""
        return self.role in (Role.SUPER_ADMIN, Role.MANAGER, Role.ADMIN)

    @property
    def is_tv(self):
        return self.role == Role.TV

    @property
    def role_label(self):
        return Role.LABELS.get(self.role, self.role)

    @property
    def active_timer(self):
        return TimeLog.query.filter_by(user_id=self.id, ended_at=None).first()


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    head = db.Column(db.String(200), nullable=False, default='', server_default='')


class TaskType(db.Model):
    __tablename__ = 'task_types'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    label = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Task(db.Model):
    __tablename__ = 'tasks'
    __table_args__ = (
        Index('ix_tasks_status', 'status'),
        Index('ix_tasks_archived', 'is_archived'),
        Index('ix_tasks_urgency', 'urgency'),
        Index('ix_tasks_deadline', 'deadline'),
        Index('ix_tasks_assigned_to', 'assigned_to_id'),
        Index('ix_tasks_department', 'department_id'),
        Index('ix_tasks_created_by', 'created_by_id'),
        Index('ix_tasks_completed_at', 'completed_at'),
        Index('ix_tasks_created_at', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(50))
    customer_email = db.Column(db.String(200))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    task_type = db.Column(db.String(50))
    urgency = db.Column(db.String(20), default=Urgency.NORMAL)
    status = db.Column(db.String(20), default=TaskStatus.NEW)
    deadline = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    parent_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    tags = db.Column(db.JSON, default=list)
    dynamic_fields = db.Column(db.JSON, default=dict)
    is_archived = db.Column(db.Boolean, default=False)
    is_external = db.Column(db.Boolean, default=False)
    archived_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department = db.relationship('Department', backref='tasks')
    created_by = db.relationship('User', backref='created_tasks', foreign_keys=[created_by_id])
    assigned_to = db.relationship('User', backref='assigned_tasks', foreign_keys=[assigned_to_id])
    attachments = db.relationship('TaskAttachment', backref='task', lazy='dynamic')
    time_logs = db.relationship('TimeLog', backref='task', lazy='dynamic')
    comments = db.relationship('TaskComment', backref='task', lazy='dynamic',
                               order_by='TaskComment.created_at')

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

    @property
    def subtasks(self):
        return Task.query.filter_by(parent_task_id=self.id, is_archived=False).all()

    @property
    def parent_task(self):
        if self.parent_task_id:
            return Task.query.get(self.parent_task_id)
        return None

    @property
    def open_subtasks_count(self):
        return Task.query.filter(
            Task.parent_task_id == self.id,
            Task.status != TaskStatus.DONE,
            Task.is_archived == False
        ).count()

    @property
    def can_close(self):
        return self.open_subtasks_count == 0


class TaskAttachment(db.Model):
    __tablename__ = 'task_attachments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    filename = db.Column(db.String(255))
    original_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    yadisk_path = db.Column(db.String(1000), nullable=True)        # путь к файлу на Яндекс Диске
    yadisk_url = db.Column(db.String(1000), nullable=True)         # публичная ссылка на файл
    yadisk_folder_url = db.Column(db.String(1000), nullable=True)  # публичная ссылка на папку


class TaskComment(db.Model):
    __tablename__ = 'task_comments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text)
    filename = db.Column(db.String(255))      # legacy single-file field
    original_name = db.Column(db.String(255)) # legacy single-file field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='comments')
    attachments = db.relationship('CommentAttachment', backref='comment',
                                  lazy='dynamic', cascade='all, delete-orphan')


class CommentAttachment(db.Model):
    __tablename__ = 'comment_attachments'
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('task_comments.id'), nullable=False)
    filename = db.Column(db.String(255))
    original_name = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    yadisk_path = db.Column(db.String(1000), nullable=True)        # путь к файлу на Яндекс Диске
    yadisk_url = db.Column(db.String(1000), nullable=True)         # публичная ссылка на файл
    yadisk_folder_url = db.Column(db.String(1000), nullable=True)  # публичная ссылка на папку


class TimeLog(db.Model):
    __tablename__ = 'time_logs'
    __table_args__ = (
        Index('ix_timelogs_user_ended', 'user_id', 'ended_at'),
        Index('ix_timelogs_task', 'task_id'),
        Index('ix_timelogs_started_at', 'started_at'),
    )
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


class Rhythm(db.Model):
    __tablename__ = 'rhythms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    frequency = db.Column(db.String(20), nullable=False, default=RhythmFrequency.DAILY)
    day_of_week = db.Column(db.Integer)    # 0-6 (Mon-Sun) for weekly
    day_of_month = db.Column(db.Integer)   # 1-31 for monthly
    trigger_time = db.Column(db.String(5))  # HH:MM, e.g. "09:00"
    task_title = db.Column(db.String(500), nullable=False)
    task_description = db.Column(db.Text)
    task_tags = db.Column(db.JSON, default=list)
    task_urgency = db.Column(db.String(20), default=Urgency.NORMAL)
    task_type = db.Column(db.String(50))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    department = db.relationship('Department', backref='rhythms')
    created_by = db.relationship('User', backref='created_rhythms', foreign_keys=[created_by_id])

    @property
    def is_due(self):
        """True if this rhythm should fire now but hasn't yet today."""
        if not self.is_active:
            return False
        from datetime import timedelta as td
        TZ = 3  # МСК offset
        now_local = datetime.utcnow() + td(hours=TZ)
        today = now_local.date()

        if self.last_run_at:
            last_local = self.last_run_at + td(hours=TZ)
            if last_local.date() == today:
                return False

        # Check day
        day_ok = False
        if self.frequency == RhythmFrequency.DAILY:
            day_ok = True
        elif self.frequency == RhythmFrequency.WEEKLY:
            day_ok = today.weekday() == (self.day_of_week or 0)
        elif self.frequency == RhythmFrequency.MONTHLY:
            day_ok = today.day == (self.day_of_month or 1)
        if not day_ok:
            return False

        # Check time (if set, fire only after that time)
        if self.trigger_time:
            try:
                hh, mm = map(int, self.trigger_time.split(':'))
                fire_at = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
                return now_local >= fire_at
            except (ValueError, AttributeError):
                pass
        return True

    @property
    def schedule_label(self):
        t = f' в {self.trigger_time}' if self.trigger_time else ''
        if self.frequency == RhythmFrequency.DAILY:
            return f'Ежедневно{t}'
        if self.frequency == RhythmFrequency.WEEKLY:
            day = RhythmFrequency.WEEKDAYS[self.day_of_week or 0]
            return f'Еженедельно ({day}){t}'
        if self.frequency == RhythmFrequency.MONTHLY:
            return f'Ежемесячно ({self.day_of_month or 1}-го){t}'
        return self.frequency


class PlanGroup(db.Model):
    __tablename__ = 'plan_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.relationship('User', backref='created_plan_groups', foreign_keys=[created_by_id])


class Plan(db.Model):
    __tablename__ = 'plans'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    customer_name = db.Column(db.String(200))
    customer_phone = db.Column(db.String(50))
    customer_email = db.Column(db.String(200))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    task_type = db.Column(db.String(50))
    urgency = db.Column(db.String(20), default=Urgency.NORMAL)
    tags = db.Column(db.JSON, default=list)
    dynamic_fields = db.Column(db.JSON, default=dict)
    group_id = db.Column(db.Integer, db.ForeignKey('plan_groups.id'), nullable=True)
    release_date = db.Column(db.DateTime, nullable=True)
    is_converted = db.Column(db.Boolean, default=False)
    converted_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship('Department', backref='plans')
    group = db.relationship('PlanGroup', backref='plans')
    created_by = db.relationship('User', backref='created_plans', foreign_keys=[created_by_id])

    @property
    def is_due(self):
        return bool(self.release_date and self.release_date <= datetime.utcnow() and not self.is_converted)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
