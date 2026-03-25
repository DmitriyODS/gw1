"""
Yandex Disk integration stub.

Планируемый функционал:
- Подключение к Яндекс Диску через OAuth-токен
- Создание папок под задачи (структура: /GrooveWork/tasks/<task_id>/)
- Загрузка файлов задачи в соответствующую папку
- Получение публичной ссылки на папку

Для активации потребуется:
- Зарегистрировать приложение на https://oauth.yandex.ru
- Добавить переменную окружения YANDEX_DISK_TOKEN в .env
- Установить зависимость: pip install yadisk
"""

# import os
# import yadisk  # pip install yadisk


TASK_FOLDER_PREFIX = '/GrooveWork/tasks'


class YandexDiskService:
    """Service for uploading task files to Yandex Disk."""

    def __init__(self, token: str | None = None):
        """
        Initialize service with OAuth token.

        Args:
            token: Yandex Disk OAuth token. If None, read from env YANDEX_DISK_TOKEN.
        """
        # self.token = token or os.environ.get('YANDEX_DISK_TOKEN')
        # self.client = yadisk.YaDisk(token=self.token) if self.token else None
        self.token = token
        self.client = None  # placeholder

    def is_configured(self) -> bool:
        """Returns True if the service has a valid token."""
        return bool(self.token)

    def ensure_task_folder(self, task_id: int) -> str:
        """
        Create folder for task if it doesn't exist.

        Args:
            task_id: Task ID used as folder name.

        Returns:
            Path to the task folder on Yandex Disk.
        """
        folder_path = f'{TASK_FOLDER_PREFIX}/{task_id}'
        # if self.client:
        #     if not self.client.exists(TASK_FOLDER_PREFIX):
        #         self.client.mkdir(TASK_FOLDER_PREFIX)
        #     if not self.client.exists(folder_path):
        #         self.client.mkdir(folder_path)
        raise NotImplementedError('Yandex Disk integration is not yet configured.')
        return folder_path

    def upload_file(self, local_path: str, task_id: int, filename: str) -> str:
        """
        Upload a file to the task folder on Yandex Disk.

        Args:
            local_path: Local file path to upload.
            task_id: Task ID to determine target folder.
            filename: Original filename to use on Yandex Disk.

        Returns:
            Public URL of the uploaded file.
        """
        folder_path = self.ensure_task_folder(task_id)
        remote_path = f'{folder_path}/{filename}'
        # self.client.upload(local_path, remote_path, overwrite=True)
        # self.client.publish(remote_path)
        # meta = self.client.get_meta(remote_path)
        # return meta.public_url
        raise NotImplementedError('Yandex Disk integration is not yet configured.')

    def upload_task_attachments(self, task_id: int, upload_folder: str) -> str:
        """
        Upload all attachments of a task to Yandex Disk.

        Args:
            task_id: Task ID.
            upload_folder: Local folder where files are stored.

        Returns:
            Public URL to the task folder on Yandex Disk.
        """
        from models import TaskAttachment
        folder_path = self.ensure_task_folder(task_id)
        attachments = TaskAttachment.query.filter_by(task_id=task_id).all()
        for att in attachments:
            import os
            local_path = os.path.join(upload_folder, att.filename)
            if os.path.exists(local_path):
                self.upload_file(local_path, task_id, att.original_name or att.filename)
        # Publish folder and return public URL
        # self.client.publish(folder_path)
        # meta = self.client.get_meta(folder_path)
        # return meta.public_url
        raise NotImplementedError('Yandex Disk integration is not yet configured.')


# Singleton instance — initialize with token when ready
# from flask import current_app
# yadisk_service = YandexDiskService(token=current_app.config.get('YANDEX_DISK_TOKEN'))
