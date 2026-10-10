"""
Attachment storage on the local filesystem (a Docker volume in compose).

Safety rules:
* Files are stored under a random name; the user-supplied name is only metadata.
* Only an allow-list of extensions is accepted, and the stored content type comes from that
  extension, never from the client. HTML, SVG and scripts are therefore never accepted.
* Size is enforced while streaming, so an oversized upload is cut off early and cleaned up.
* Downloads are always sent as attachments with `nosniff` (see api/tasks.py).
"""

import asyncio
import logging
import re
import uuid
from pathlib import Path
from typing import Protocol

from config import settings
from exceptions import OrbitException

logger = logging.getLogger(__name__)

CHUNK_BYTES = 64 * 1024

ALLOWED_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".log": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}


class UploadRejected(OrbitException):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message=message, status_code=status_code)


class _Readable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


def upload_root() -> Path:
    root = Path(settings.UPLOAD_DIR)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def max_upload_bytes() -> int:
    return settings.MAX_UPLOAD_MB * 1024 * 1024


def clean_filename(raw: str | None) -> str:
    """Display name only: no path parts, no control characters, bounded length."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "", name).strip(" .")
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 195 - len(ext)] + dot + ext) if dot else name[:200]
    return name


def validate_filename(raw: str | None) -> tuple[str, str]:
    """Returns (display_name, content_type) or raises UploadRejected."""
    name = clean_filename(raw)
    if not name:
        raise UploadRejected("The file needs a name.")
    ext = Path(name).suffix.lower()
    content_type = ALLOWED_TYPES.get(ext)
    if content_type is None:
        allowed = ", ".join(sorted(e.lstrip(".") for e in ALLOWED_TYPES))
        raise UploadRejected(f"Files of type '{ext or 'unknown'}' are not allowed. Allowed: {allowed}.", 415)
    return name, content_type


def path_for(stored_name: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", stored_name):
        raise ValueError("invalid stored name")
    return upload_root() / stored_name


async def save_stream(source: _Readable) -> tuple[str, int]:
    """Writes the upload to disk, enforcing the size cap. Returns (stored_name, size)."""
    stored_name = uuid.uuid4().hex
    target = path_for(stored_name)
    limit = max_upload_bytes()
    size = 0
    loop = asyncio.get_running_loop()
    try:
        with open(target, "wb") as handle:
            while True:
                chunk = await source.read(CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise UploadRejected(f"File is larger than {settings.MAX_UPLOAD_MB} MB.", 413)
                await loop.run_in_executor(None, handle.write, chunk)
        if size == 0:
            raise UploadRejected("The file is empty.")
    except BaseException:
        remove(stored_name)
        raise
    return stored_name, size


def remove(stored_name: str) -> None:
    """Best effort: a missing file must never block deleting its record."""
    try:
        path_for(stored_name).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Could not remove stored file %s: %s", stored_name, exc)
