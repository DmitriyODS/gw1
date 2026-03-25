import os
from datetime import datetime
from flask import Flask, redirect, url_for
from flask_login import current_user
from extensions import db, login_manager, csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(media_plan_bp)
    app.register_blueprint(rhythms_bp)
    app.register_blueprint(plans_bp)

    @app.context_processor
    def inject_avatar_v():
        v = 0
        try:
            if current_user.is_authenticated:
                p = os.path.join(app.root_path, 'static', 'avatars',
                                 f'{current_user.id}.png')
                if os.path.exists(p):
                    v = int(os.path.getmtime(p))
        except Exception:
            pass
        return {'avatar_v': v}

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
        ]
        for table, col, col_type in cols:
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}'))
                    conn.commit()
                print(f'Added {table}.{col}')
            except Exception as e:
                print(f'Skipped {table}.{col}: {e}')
        # Create new tables (rhythms etc.)
        db.create_all()
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
        tasks = Task.query.filter(
            db.or_(
                Task.customer_name == 'None',
                Task.customer_phone == 'None',
                Task.customer_email == 'None',
            )
        ).all()
        count = 0
        for t in tasks:
            if t.customer_name == 'None':
                t.customer_name = None
                count += 1
            if t.customer_phone == 'None':
                t.customer_phone = None
                count += 1
            if t.customer_email == 'None':
                t.customer_email = None
                count += 1
        db.session.commit()
        print(f'Fixed {count} fields in {len(tasks)} tasks')

    @app.cli.command('auto-archive')
    def auto_archive_cmd():
        """Archive all done tasks older than 7 days. Run weekly via cron."""
        from datetime import datetime, timedelta
        from models import Task, TaskStatus
        now = datetime.utcnow()
        cutoff = now - timedelta(days=7)
        tasks = Task.query.filter(
            Task.status == TaskStatus.DONE,
            Task.completed_at < cutoff,
            Task.completed_at.isnot(None),
            Task.is_archived == False,
        ).all()
        for t in tasks:
            t.is_archived = True
            t.archived_at = now
        db.session.commit()
        print(f'Archived {len(tasks)} tasks')

    @app.cli.command('archive-old')
    def archive_old():
        from datetime import datetime, timedelta
        from models import Task, TaskStatus
        cutoff = datetime.utcnow() - timedelta(days=365)
        tasks = Task.query.filter(
            Task.created_at < cutoff,
            Task.is_archived == False,
            Task.status == TaskStatus.DONE
        ).all()
        for t in tasks:
            t.is_archived = True
            t.archived_at = datetime.utcnow()
        db.session.commit()
        print(f'Archived {len(tasks)} tasks')

    return app
