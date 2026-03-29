import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://tasktime:tasktime@localhost:5432/tasktime')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 1800,   # пересоздавать соединения каждые 30 минут
        'pool_pre_ping': True,  # проверять соединение перед использованием
    }
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    ALLOWED_EXTENSIONS = None  # allow all file types
    MAX_CONTENT_LENGTH = 550 * 1024 * 1024  # 550MB (файлы до 500MB + overhead)
    WTF_CSRF_TIME_LIMIT = None
    TZ_OFFSET_HOURS = int(os.environ.get('TZ_OFFSET_HOURS', 3))
    YANDEX_DISK_TOKEN = os.environ.get('YANDEX_DISK_TOKEN', 'y0__xDNucmSBBipvz8go7yz8BaVcBPY08qSol9gfTloi8DUYooOag')

    # ── Почта (IMAP/SMTP) ──
    MAIL_IMAP_HOST   = os.environ.get('MAIL_IMAP_HOST',   'mail.bmstu.ru')
    MAIL_IMAP_PORT   = int(os.environ.get('MAIL_IMAP_PORT', 993))
    MAIL_SMTP_HOST   = os.environ.get('MAIL_SMTP_HOST',   'mail.bmstu.ru')
    MAIL_SMTP_PORT   = int(os.environ.get('MAIL_SMTP_PORT', 465))
    MAIL_USER        = os.environ.get('MAIL_USER',        'osipovskiy.ds')
    MAIL_PASSWORD    = os.environ.get('MAIL_PASSWORD',    'BmstuOsipo2025')
    MAIL_FROM_EMAIL  = os.environ.get('MAIL_FROM_EMAIL',  'info.kf@bmstu.ru')
    MAIL_FROM_NAME   = os.environ.get('MAIL_FROM_NAME',   'Отдел региональных коммуникаций (Калуга) МГТУ им. Н.Э. Баумана')
    # Для корпоративных серверов с внутренними сертификатами — False
    MAIL_VERIFY_SSL  = os.environ.get('MAIL_VERIFY_SSL',  'false').lower() == 'true'
    MAIL_INBOX_FOLDER = os.environ.get('MAIL_INBOX_FOLDER', 'info.kf')
    MAIL_SENT_FOLDER  = os.environ.get('MAIL_SENT_FOLDER',  'Sent')
    # SMTP: 'ssl' = SMTP_SSL (порт 465), 'starttls' = SMTP+STARTTLS (порт 587)
    MAIL_SMTP_MODE   = os.environ.get('MAIL_SMTP_MODE',   'ssl')
