import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://tasktime:tasktime@localhost:5432/tasktime')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/app/uploads')
    ALLOWED_EXTENSIONS = None  # allow all file types
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    WTF_CSRF_TIME_LIMIT = None
    TZ_OFFSET_HOURS = int(os.environ.get('TZ_OFFSET_HOURS', 3))
