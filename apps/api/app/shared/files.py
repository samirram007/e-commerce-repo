"""File/object storage abstraction.

Private by default: file metadata lives in the database, contents go to
`MEDIA_DIR` (swap for S3-compatible object storage in production by replacing
`save_file`/`open_file`). Keys are generated server-side — client filenames are
never trusted. Downloads must pass through authorized endpoints.
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import BigInteger, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.security import new_id
from app.db.base import Base, TimestampMixin, CreatedByMixin

ALLOWED_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}

#: Content types accepted for storefront imagery (product/category/hero photos).
IMAGE_CONTENT_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class StoredFile(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    storage_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="generic", index=True)
    # ---- library placement (see app/modules/files) ----
    folder_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    #: Who put the file here: `erp` (staff), `storefront` (shopper) or `system`.
    uploaded_via: Mapped[str] = mapped_column(String(16), nullable=False, default="erp", server_default="erp")
    #: Shopper identity for storefront uploads (`user:<id>` / `anon:<id>`).
    owner_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # ---- trash ----
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


def _media_root() -> Path:
    root = Path(get_settings().media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_upload(
    upload: UploadFile,
    *,
    purpose: str = "generic",
    allowed_types: set[str] | None = None,
) -> dict:
    """Stream an upload to disk under `purpose/` and describe it.

    Returns the metadata a `StoredFile` (or a new version) needs; the caller
    owns the database row, so replacing a file's content reuses this too.
    """
    settings = get_settings()
    allowed = allowed_types or ALLOWED_CONTENT_TYPES
    content_type = upload.content_type or "application/octet-stream"
    if content_type not in allowed:
        raise BusinessRuleError(
            "UNSUPPORTED_FILE_TYPE", f"File type '{content_type}' is not allowed"
        )
    size = 0
    chunks: list[bytes] = []
    while chunk := upload.file.read(1024 * 512):
        size += len(chunk)
        if size > settings.max_upload_mb * 1024 * 1024:
            raise BusinessRuleError(
                "FILE_TOO_LARGE", f"Upload exceeds {settings.max_upload_mb} MB limit"
            )
        chunks.append(chunk)
    if size == 0:
        raise BusinessRuleError("EMPTY_FILE", "Uploaded file is empty")

    suffix = allowed[content_type]
    storage_key = f"{purpose}/{uuid.uuid4().hex}{suffix}"
    dest = _media_root() / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        for chunk in chunks:
            fh.write(chunk)
    return {
        "storage_key": storage_key,
        "original_name": upload.filename or "upload",
        "content_type": content_type,
        "size_bytes": size,
    }


def save_file(
    session: Session,
    upload: UploadFile,
    *,
    company_id: str | None,
    purpose: str = "generic",
    created_by: str | None = None,
    allowed_types: set[str] | None = None,
    visibility: str = "private",
    folder_id: str | None = None,
    uploaded_via: str = "erp",
    owner_key: str | None = None,
    order_id: str | None = None,
) -> StoredFile:
    if visibility not in {"private", "public"}:
        raise BusinessRuleError("BAD_FILE_VISIBILITY", "visibility must be 'private' or 'public'")
    stored = store_upload(upload, purpose=purpose, allowed_types=allowed_types)
    record = StoredFile(
        company_id=company_id,
        visibility=visibility,
        purpose=purpose,
        folder_id=folder_id,
        uploaded_via=uploaded_via,
        owner_key=owner_key,
        order_id=order_id,
        created_by=created_by,
        **stored,
    )
    session.add(record)
    session.flush()
    if record.folder_id is None and company_id:
        # Late import: the library module builds on this one, so the cycle has
        # to be broken at call time. Uploads made by other screens (product
        # images, storefront media, payslips) land in their purpose folder
        # instead of loose at the library root.
        from app.modules.files import service as files_service

        files_service.file_upload(
            session, company_id=company_id, record=record, actor_user_id=created_by
        )
    return record


def open_file(session: Session, file_id: str, *, company_id: str | None) -> tuple[StoredFile, Path]:
    record = session.get(StoredFile, file_id)
    if record is None:
        raise NotFoundError("File")
    if record.visibility == "private" and record.company_id != company_id:
        raise NotFoundError("File")  # do not reveal existence across tenants
    path = _media_root() / record.storage_key
    if not path.is_file():
        raise NotFoundError("File contents")
    return record, path


def open_public_file(session: Session, file_id: str, *, company_id: str | None) -> tuple[StoredFile, Path]:
    """Open a file for the headerless public image route.

    Only files explicitly saved with `visibility="public"` and belonging to the
    company named in the URL are served; everything else (including cross-tenant
    existence) is a 404 so private documents are never revealed.
    """
    record = session.get(StoredFile, file_id)
    if record is None or record.visibility != "public" or record.company_id != company_id:
        raise NotFoundError("File")
    path = _media_root() / record.storage_key
    if not path.is_file():
        raise NotFoundError("File contents")
    return record, path


def delete_file(session: Session, file_id: str) -> None:
    record = session.get(StoredFile, file_id)
    if record is None:
        return
    discard_contents(record.storage_key)
    session.delete(record)


def discard_contents(storage_key: str) -> None:
    """Remove stored bytes (used by purge and by version replacement)."""
    path = _media_root() / storage_key
    if path.is_file():
        path.unlink()
