import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
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
