import os
from datetime import datetime
from flask import Flask, redirect, url_for
from flask_login import current_user
from extensions import db, login_manager, csrf, jwt


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Необходима авторизация'
    login_manager.login_message_category = 'warning'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from blueprints.auth import auth_bp
    from blueprints.public import public_bp
    from blueprints.tasks import tasks_bp
    from blueprints.analytics import analytics_bp
    from blueprints.admin_bp import admin_bp
    from blueprints.profile import profile_bp
    from blueprints.media_plan import media_plan_bp
    from blueprints.rhythms import rhythms_bp
    from blueprints.plans import plans_bp
    from blueprints.lists_bp import lists_bp
    from blueprints.mail_bp import mail_bp
    from blueprints.api_v1 import api_v1_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(media_plan_bp)
    app.register_blueprint(rhythms_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(lists_bp)
    app.register_blueprint(mail_bp)
    app.register_blueprint(api_v1_bp)
    csrf.exempt(api_v1_bp)

    # JWT: загружать пользователя из identity (id)
    from models import User

    @jwt.user_lookup_loader
    def _user_lookup(_jwt_header, jwt_data):
        return User.query.filter_by(
            id=int(jwt_data['sub']), is_active=True
        ).one_or_none()

    @app.context_processor
    def inject_avatar_v():
        v = 0
        active_timer = None
        try:
            if current_user.is_authenticated:
                p = os.path.join(app.root_path, 'static', 'avatars',
                                 f'{current_user.id}.png')
                if os.path.exists(p):
                    v = int(os.path.getmtime(p))
                # Активный таймер для topbar — один раз на запрос через context processor
                # вместо вызова current_user.active_timer прямо в base.html
                from models import TimeLog
                active_timer = TimeLog.query.filter_by(
                    user_id=current_user.id, ended_at=None
                ).first()
        except Exception:
            pass
        from models import Role
        return {'avatar_v': v, 'current_user_active_timer': active_timer, 'Role': Role}

    @app.route('/')
    def index():
        return redirect(url_for('tasks.list_tasks'))

    @app.template_filter('duration')
    def duration_filter(seconds):
        if not seconds:
            return '0 мин'
        seconds = int(seconds)
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if d:
            return f'{d}д {h}ч {m}мин'
        if h:
            return f'{h}ч {m}мин'
        if m:
            return f'{m}мин {s}с'
        return f'{s}с'

    @app.template_filter('timeformat')
    def timeformat_filter(dt):
        if not dt:
            return ''
        from datetime import timedelta
        tz_offset = timedelta(hours=app.config.get('TZ_OFFSET_HOURS', 3))
        return (dt + tz_offset).strftime('%d.%m.%Y %H:%M')

    @app.template_filter('shorttime')
    def shorttime_filter(dt):
        if not dt:
            return ''
        from datetime import timedelta
        tz_offset = timedelta(hours=app.config.get('TZ_OFFSET_HOURS', 3))
        return (dt + tz_offset).strftime('%d.%m %H:%M')

    @app.template_filter('localdate')
    def localdate_filter(dt):
        """Convert UTC datetime to local date object."""
        if not dt:
            return None
        from datetime import timedelta
        tz_offset = timedelta(hours=app.config.get('TZ_OFFSET_HOURS', 3))
        return (dt + tz_offset).date()

    @app.template_filter('hhmm')
    def hhmm_filter(dt):
        """Format UTC datetime as HH:MM in local time."""
        if not dt:
            return ''
        from datetime import timedelta
        tz_offset = timedelta(hours=app.config.get('TZ_OFFSET_HOURS', 3))
        return (dt + tz_offset).strftime('%H:%M')

    @app.cli.command('migrate-db')
    def migrate_db():
        """Add new columns to existing tables without dropping data."""
        cols = [
            ('tasks', 'completed_at',    'TIMESTAMP'),
            ('tasks', 'assigned_to_id',  'INTEGER REFERENCES users(id)'),
            ('tasks', 'parent_task_id',  'INTEGER REFERENCES tasks(id)'),
            ('tasks', 'tags',            'JSON'),
            ('tasks', 'customer_email',  'VARCHAR(200)'),
            ('plans', 'release_date',    'TIMESTAMP'),
            ('plans', 'customer_email',  'VARCHAR(200)'),
            ('tasks', 'updated_at',      'TIMESTAMP'),
            ('task_comments', 'filename',     'VARCHAR(255)'),
            ('task_comments', 'original_name','VARCHAR(255)'),
            ('rhythms',       'trigger_time', 'VARCHAR(5)'),
            ('departments',   'head',         "VARCHAR(200) NOT NULL DEFAULT ''"),
            ('comment_attachments', 'yadisk_path',       'VARCHAR(1000)'),
            ('comment_attachments', 'yadisk_url',        'VARCHAR(1000)'),
            ('comment_attachments', 'yadisk_folder_url', 'VARCHAR(1000)'),
            ('task_attachments',    'yadisk_path',       'VARCHAR(1000)'),
            ('task_attachments',    'yadisk_url',        'VARCHAR(1000)'),
            ('task_attachments',    'yadisk_folder_url', 'VARCHAR(1000)'),
            ('users', 'mail_user',     'VARCHAR(200)'),
            ('users', 'mail_password', 'VARCHAR(200)'),
            ('tasks', 'is_external',   'BOOLEAN DEFAULT FALSE'),
            ('task_types', 'coefficient', 'FLOAT NOT NULL DEFAULT 1.0'),
        ]
        for table, col, col_type in cols:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}'))
                    conn.commit()
                print(f'Added {table}.{col}')
            except Exception as e:
                print(f'Skipped {table}.{col}: {e}')
        # Create new indexes (IF NOT EXISTS — безопасно запускать повторно)
        new_indexes = [
            ('ix_tasks_assigned_to',  'CREATE INDEX IF NOT EXISTS ix_tasks_assigned_to  ON tasks (assigned_to_id)'),
            ('ix_tasks_department',   'CREATE INDEX IF NOT EXISTS ix_tasks_department   ON tasks (department_id)'),
            ('ix_tasks_created_by',   'CREATE INDEX IF NOT EXISTS ix_tasks_created_by   ON tasks (created_by_id)'),
            ('ix_tasks_completed_at', 'CREATE INDEX IF NOT EXISTS ix_tasks_completed_at ON tasks (completed_at)'),
            ('ix_tasks_created_at',   'CREATE INDEX IF NOT EXISTS ix_tasks_created_at   ON tasks (created_at)'),
            ('ix_timelogs_user_ended','CREATE INDEX IF NOT EXISTS ix_timelogs_user_ended ON time_logs (user_id, ended_at)'),
            ('ix_timelogs_task',      'CREATE INDEX IF NOT EXISTS ix_timelogs_task       ON time_logs (task_id)'),
            ('ix_timelogs_started_at','CREATE INDEX IF NOT EXISTS ix_timelogs_started_at ON time_logs (started_at)'),
        ]
        for name, sql in new_indexes:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text(sql))
                    conn.commit()
                print(f'Index {name} OK')
            except Exception as e:
                print(f'Skipped index {name}: {e}')
        # Create new tables (rhythms, task_types etc.)
        db.create_all()
        # Seed task_types from hardcoded list if table is empty
        from models import TaskType
        from blueprints.public import TASK_TYPES
        if not TaskType.query.first():
            for i, (slug, label) in enumerate(TASK_TYPES):
                db.session.add(TaskType(slug=slug, label=label, sort_order=i))
            db.session.commit()
            print(f'Task types seeded: {len(TASK_TYPES)} types')
        print('Migration complete')

    @app.cli.command('init-db')
    def init_db():
        db.create_all()
        from models import User, Role, Department
        if not User.query.filter_by(role=Role.SUPER_ADMIN).first():
            admin = User(
                username='admin',
                email='admin@tasktime.local',
                full_name='Super Admin',
                role=Role.SUPER_ADMIN,
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Super Admin: admin / admin123')

        if not Department.query.first():
            for name in ['IT отдел', 'Маркетинг', 'HR', 'Бухгалтерия', 'Производство']:
                db.session.add(Department(name=name))
            db.session.commit()
            print('Departments seeded')

        from models import TaskType
        from blueprints.public import TASK_TYPES
        if not TaskType.query.first():
            for i, (slug, label) in enumerate(TASK_TYPES):
                db.session.add(TaskType(slug=slug, label=label, sort_order=i))
            db.session.commit()
            print(f'Task types seeded: {len(TASK_TYPES)} types')

        print('DB initialized!')

    @app.cli.command('migrate-review')
    def migrate_review_cmd():
        """Move all tasks with status=review to done."""
        from models import Task, TaskStatus
        now = datetime.now()
        tasks = Task.query.filter_by(status='review').all()
        count = len(tasks)
        for t in tasks:
            t.status = TaskStatus.DONE
            if not t.completed_at:
                t.completed_at = now
        db.session.commit()
        print(f'Done: {count} tasks moved from review → done')

    @app.cli.command('fix-none-fields')
    def fix_none_fields():
        """Clear literal 'None' string values from customer fields."""
        from models import Task
        c1 = Task.query.filter(Task.customer_name == 'None').update(
            {'customer_name': None}, synchronize_session=False)
        c2 = Task.query.filter(Task.customer_phone == 'None').update(
            {'customer_phone': None}, synchronize_session=False)
        c3 = Task.query.filter(Task.customer_email == 'None').update(
            {'customer_email': None}, synchronize_session=False)
        db.session.commit()
        print(f'Fixed {c1 + c2 + c3} fields')

    @app.cli.command('auto-archive')
    def auto_archive_cmd():
        """Archive all done tasks older than 7 days. Run weekly via cron."""
        from datetime import datetime, timedelta
        from models import Task, TaskStatus
        now = datetime.utcnow()
        cutoff = now - timedelta(days=7)
        count = Task.query.filter(
            Task.status == TaskStatus.DONE,
            Task.completed_at < cutoff,
            Task.completed_at.isnot(None),
            Task.is_archived == False,
        ).update({'is_archived': True, 'archived_at': now}, synchronize_session=False)
        db.session.commit()
        print(f'Archived {count} tasks')

    @app.cli.command('fix-done-assignees')
    def fix_done_assignees():
        """Clear assigned_to_id for all done tasks (one-time cleanup)."""
        from models import Task, TaskStatus
        count = Task.query.filter(
            Task.status == TaskStatus.DONE,
            Task.assigned_to_id.isnot(None),
        ).update({'assigned_to_id': None}, synchronize_session=False)
        db.session.commit()
        print(f'Cleared assigned_to_id for {count} done tasks')

    @app.cli.command('fix-sequences')
    def fix_sequences():
        """Reset PostgreSQL ID sequences to max(id) — run after manual data import."""
        tables = ['users', 'departments', 'tasks', 'task_attachments',
                  'task_comments', 'time_logs']
        with db.engine.connect() as conn:
            for table in tables:
                result = conn.execute(db.text(
                    f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 1))"
                ))
                val = result.scalar()
                print(f'{table}_id_seq → {val}')
            conn.commit()
        print('Sequences fixed')

    @app.cli.command('archive-old')
    def archive_old():
        from datetime import datetime, timedelta
        from models import Task, TaskStatus
        now = datetime.utcnow()
        cutoff = now - timedelta(days=365)
        count = Task.query.filter(
            Task.created_at < cutoff,
            Task.is_archived == False,
            Task.status == TaskStatus.DONE
        ).update({'is_archived': True, 'archived_at': now}, synchronize_session=False)
        db.session.commit()
        print(f'Archived {count} tasks')

    return app
