"""
DriveService — singleton-клиент Google Drive API v3 (Service Account).

Синхронный google-api-python-client оборачиваем в asyncio.to_thread,
чтобы не блокировать event loop aiogram.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bot.config import settings

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"

# Регулярка для извлечения folder_id из ссылки или сырого ID
_ID_RE = re.compile(r"[-\w]{25,}")


class DriveError(Exception):
    """Базовая ошибка работы с Drive."""


class DriveAccessError(DriveError):
    """Нет доступа / папка не найдена."""


def extract_folder_id(text: str) -> str | None:
    """Достаёт folder_id из ссылки Google Drive или возвращает сырой ID."""
    if not text:
        return None
    m = _ID_RE.search(text.strip())
    return m.group(0) if m else None


class DriveService:
    _instance: "DriveService | None" = None

    def __init__(self) -> None:
        creds = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file, scopes=SCOPES
        )
        # cache_discovery=False — чтобы не ругался в async-окружении
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        log.info("DriveService инициализирован (SA: %s)", self.service_account_email)

    # --- singleton ---
    @classmethod
    def get(cls) -> "DriveService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # --- email сервисного аккаунта (для онбординга) ---
    @property
    def service_account_email(self) -> str:
        return _read_sa_email(settings.google_service_account_file)

    # --- низкоуровневый вызов в потоке ---
    async def _run(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    # --- API ---
    async def get_item(self, file_id: str, with_parents: bool = False) -> dict[str, Any]:
        """Метаданные элемента. Бросает DriveAccessError при 403/404."""
        fields = "id, name, mimeType"
        if with_parents:
            fields += ", parents"

        def _call():
            return (
                self._service.files()
                .get(fileId=file_id, fields=fields, supportsAllDrives=True)
                .execute()
            )

        try:
            return await self._run(_call)
        except HttpError as e:
            status = getattr(e, "status_code", None) or e.resp.status
            if status in (403, 404):
                raise DriveAccessError(str(e)) from e
            raise DriveError(str(e)) from e

    async def validate_folder(self, file_id: str) -> dict[str, Any]:
        """Проверяет, что элемент существует и это папка."""
        item = await self.get_item(file_id)
        if item.get("mimeType") != FOLDER_MIME:
            raise DriveError("Это не папка Google Drive.")
        return item

    async def list_children(self, folder_id: str) -> list[dict[str, Any]]:
        """Список дочерних элементов: папки перед файлами, сортировка по имени."""
        def _call():
            results: list[dict[str, Any]] = []
            page_token = None
            while True:
                resp = (
                    self._service.files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed = false",
                        fields="nextPageToken, files(id, name, mimeType)",
                        orderBy="folder,name",
                        pageSize=1000,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )
                results.extend(resp.get("files", []))
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            return results

        try:
            items = await self._run(_call)
        except HttpError as e:
            status = getattr(e, "status_code", None) or e.resp.status
            if status in (403, 404):
                raise DriveAccessError(str(e)) from e
            raise DriveError(str(e)) from e

        folders = [i for i in items if i.get("mimeType") == FOLDER_MIME]
        files = [i for i in items if i.get("mimeType") != FOLDER_MIME]
        folders.sort(key=lambda x: x["name"].lower())
        files.sort(key=lambda x: x["name"].lower())
        return folders + files

    async def ensure_public(self, file_id: str) -> None:
        """Делает элемент публичным (anyone/reader). 403 alreadyExists — игнор."""
        def _call():
            self._service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
                supportsAllDrives=True,
            ).execute()

        try:
            await self._run(_call)
        except HttpError as e:
            reason = ""
            try:
                data = json.loads(e.content.decode("utf-8"))
                reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
            except Exception:
                reason = str(e)
            if "alreadyExists" in reason:
                return  # уже публично — ок
            log.error("ensure_public error (%s): %s", file_id, e)
            raise DriveError(str(e)) from e

    @staticmethod
    def public_url(item_id: str, is_folder: bool) -> str:
        if is_folder:
            return f"https://drive.google.com/drive/folders/{item_id}"
        return f"https://drive.google.com/file/d/{item_id}/view"


@lru_cache(maxsize=1)
def _read_sa_email(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("client_email", "(email не найден в JSON)")
    except Exception as e:  # noqa: BLE001
        log.error("Не удалось прочитать service account email: %s", e)
        return "(не удалось прочитать service_account.json)"


def is_folder(mime_type: str) -> bool:
    return mime_type == FOLDER_MIME
