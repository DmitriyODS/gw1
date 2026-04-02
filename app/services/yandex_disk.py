"""
Yandex Disk integration via REST API (без сторонних зависимостей).

Структура папок на диске:
  Текущая работа
    └── ГГГГ.ММ.ДД
          └── <название задачи>
                ├── <ФИО сотрудника>   ← комментарии
                │     └── чч-мм-сс
                │           └── files...
                └── Вложения задачи    ← прикреплённые к задаче файлы
                      └── files...

Файлы не хранятся локально — загружаются напрямую на Яндекс Диск.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

DISK_API = 'https://cloud-api.yandex.net/v1/disk'
ROOT_FOLDER = 'Текущая работа'
TASK_ATTACH_FOLDER = 'Вложения задачи'


# ── Базовые запросы ──────────────────────────────────────────────────────────

def _request(token, method, endpoint, params=None, data=None, raw_url=None):
    url = raw_url or (DISK_API + endpoint)
    if params:
        url = url + '?' + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'OAuth {token}')
    req.add_header('Accept', 'application/json')
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
        req.data = body
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        return json.loads(content.decode('utf-8')) if content else {}


def _folder_exists(token, path):
    try:
        _request(token, 'GET', '/resources', params={'path': path})
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def _ensure_folder(token, path):
    if not _folder_exists(token, path):
        try:
            _request(token, 'PUT', '/resources', params={'path': path})
        except urllib.error.HTTPError as e:
            if e.code != 409:  # 409 = уже существует (race condition)
                raise


def _sanitize(name):
    """Убрать символы, недопустимые в именах папок/файлов YDisk."""
    sanitized = re.sub(r'[\\:*?"<>|/]', '_', name).strip()
    return sanitized[:100] or 'unnamed'


def _unique_remote_path(token, folder_path, filename):
    """
    Вернуть уникальный путь для файла в папке.
    Если файл с таким именем уже существует, добавить суффикс _2, _3, ...
    """
    base, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    candidate = f'{folder_path}/{filename}'
    if not _folder_exists(token, candidate):
        return candidate
    index = 2
    while True:
        name = f'{base}_{index}.{ext}' if ext else f'{base}_{index}'
        candidate = f'{folder_path}/{name}'
        if not _folder_exists(token, candidate):
            return candidate
        index += 1


# ── Загрузка одного файла ─────────────────────────────────────────────────────

def _upload_fileobj(token, fileobj, remote_path):
    """Загрузить файловый объект (Werkzeug FileStorage или любой file-like) на YDisk."""
    resp = _request(token, 'GET', '/resources/upload', params={
        'path': remote_path,
        'overwrite': 'false',
    })
    upload_url = resp['href']
    fileobj.seek(0)
    data = fileobj.read()
    req = urllib.request.Request(upload_url, data=data, method='PUT')
    req.add_header('Content-Type', 'application/octet-stream')
    with urllib.request.urlopen(req):
        pass  # 201 Created или 200 OK


def _publish_file(token, path):
    """Опубликовать файл/папку и вернуть публичную ссылку."""
    put_resp = _request(token, 'PUT', '/resources/publish', params={'path': path})
    if put_resp.get('public_url'):
        return put_resp['public_url']
    # GET с retry: Яндекс иногда не успевает проставить public_url сразу после publish.
    for delay in (0, 0.5, 1.5):
        if delay:
            time.sleep(delay)
        resp = _request(token, 'GET', '/resources', params={
            'path': path,
            'fields': 'public_url',
        })
        url = resp.get('public_url')
        if url:
            return url
    return None


# ── Публичный API ─────────────────────────────────────────────────────────────

def delete_resource(token, path):
    """Удалить файл или папку с Яндекс Диска безвозвратно. Молча игнорирует 404."""
    try:
        _request(token, 'DELETE', '/resources', params={
            'path': path,
            'permanently': 'true',
        })
    except urllib.error.HTTPError as e:
        if e.code not in (404, 204):
            raise


def delete_comment_files(token, yadisk_paths):
    """
    Удалить файлы комментария с Я.Диска.
    Все файлы одного комментария лежат в одной папке — удаляем её целиком.
    yadisk_paths: список путей вида 'Текущая работа/.../чч-мм-сс/file.ext'
    """
    if not yadisk_paths:
        return
    # Уникальные папки (убираем имя файла)
    folders = {'/'.join(p.split('/')[:-1]) for p in yadisk_paths if '/' in p}
    for folder in folders:
        if folder:
            delete_resource(token, folder)


def delete_file(token, yadisk_path):
    """Удалить один файл с Я.Диска."""
    if yadisk_path:
        delete_resource(token, yadisk_path)


def upload_comment_files(token, task, user, files_info, tz_offset=3):
    """
    Загрузить файлы комментария на Яндекс Диск.

    Структура:
      Текущая работа / ГГГГ.ММ.ДД / Название задачи / ФИО / чч-мм-сс / файлы

    Args:
        token: OAuth-токен
        task: объект Task
        user: объект User
        files_info: список (fileobj, original_name) — fileobj это Werkzeug FileStorage
        tz_offset: смещение от UTC (МСК = 3)

    Returns:
        file_results: список {'original_name': ..., 'yadisk_url': ..., 'yadisk_path': ...}
        folder_url: публичная ссылка на папку с файлами этого комментария
    """
    now_local = datetime.utcnow() + timedelta(hours=tz_offset)
    date_str = now_local.strftime('%Y.%m.%d')
    time_str = now_local.strftime('%H-%M-%S')

    task_folder_name = _sanitize(task.title)
    user_folder_name = _sanitize(user.full_name)

    root_path    = ROOT_FOLDER
    date_path    = f'{root_path}/{date_str}'
    task_path    = f'{date_path}/{task_folder_name}'
    user_path    = f'{task_path}/{user_folder_name}'
    comment_path = f'{user_path}/{time_str}'

    _ensure_folder(token, root_path)
    _ensure_folder(token, date_path)
    _ensure_folder(token, task_path)
    _ensure_folder(token, user_path)
    _ensure_folder(token, comment_path)

    file_results = []
    for fileobj, original_name in files_info:
        remote_path = _unique_remote_path(token, comment_path, _sanitize(original_name))
        _upload_fileobj(token, fileobj, remote_path)
        file_url = _publish_file(token, remote_path)
        file_results.append({
            'original_name': original_name,
            'yadisk_url': file_url,
            'yadisk_path': remote_path,
        })

    folder_url = _publish_file(token, comment_path)
    return file_results, folder_url


def upload_task_files(token, task, files_info, tz_offset=3):
    """
    Загрузить вложения задачи на Яндекс Диск.

    Структура:
      Текущая работа / ГГГГ.ММ.ДД / Название задачи / Вложения задачи / файлы

    Args:
        token: OAuth-токен
        task: объект Task
        files_info: список (fileobj, original_name)
        tz_offset: смещение от UTC

    Returns:
        file_results: список {'original_name': ..., 'yadisk_url': ..., 'yadisk_path': ...}
        folder_url: публичная ссылка на папку вложений
    """
    now_local = datetime.utcnow() + timedelta(hours=tz_offset)
    date_str = now_local.strftime('%Y.%m.%d')

    task_folder_name = _sanitize(task.title)
    attach_folder_name = _sanitize(TASK_ATTACH_FOLDER)

    root_path   = ROOT_FOLDER
    date_path   = f'{root_path}/{date_str}'
    task_path   = f'{date_path}/{task_folder_name}'
    attach_path = f'{task_path}/{attach_folder_name}'

    _ensure_folder(token, root_path)
    _ensure_folder(token, date_path)
    _ensure_folder(token, task_path)
    _ensure_folder(token, attach_path)

    file_results = []
    for fileobj, original_name in files_info:
        remote_path = _unique_remote_path(token, attach_path, _sanitize(original_name))
        _upload_fileobj(token, fileobj, remote_path)
        file_url = _publish_file(token, remote_path)
        file_results.append({
            'original_name': original_name,
            'yadisk_url': file_url,
            'yadisk_path': remote_path,
        })

    folder_url = _publish_file(token, attach_path)
    return file_results, folder_url
