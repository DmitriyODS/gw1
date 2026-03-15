import os
from flask import Flask, redirect, url_for
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return redirect(url_for('tasks.list_tasks'))

    @app.template_filter('duration')
    def duration_filter(seconds):
        if not seconds:
            return '0 мин'
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            return f'{h}ч {m}мин'
        if m:
            return f'{m}мин {s}с'
        return f'{s}с'

    @app.template_filter('timeformat')
    def timeformat_filter(dt):
        if not dt:
            return ''
        return dt.strftime('%d.%m.%Y %H:%M')

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
