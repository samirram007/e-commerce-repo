"""File library models: folders, versions and share links.

`StoredFile` itself lives in `app/shared/files.py` (it is the storage
abstraction every module uses); this module adds the folder tree over it, the
version history of a file, and the share links that expose one file or folder
outside the ERP.
"""
import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import new_id
from app.db.base import Base, CreatedByMixin, TimestampMixin

#: System folders features file their uploads into (created on first use).
SYSTEM_FOLDERS = {
    "general": "General",
    "product_images": "Product images",
    "storefront_media": "Storefront media",
    "shopper_uploads": "Customer uploads",
    "payroll_documents": "Payroll documents",
}


class FileFolder(Base, TimestampMixin, CreatedByMixin):
    __tablename__ = "file_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Materialised path ("/Storefront/Product images") for display and search.
    path: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    #: Set for folders the application fills itself (see SYSTEM_FOLDERS).
    system_key: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # ---- access: empty means "anyone with the files permissions" ----
    required_permission: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role_names: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[str]
    #: Shoppers may upload into this folder from the storefront (moderated inbox).
    accepts_shopper_uploads: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "parent_id", "name", name="uq_file_folder_name"),
    )

    @property
    def roles(self) -> list[str]:
        if not self.role_names:
            return []
        try:
            value = json.loads(self.role_names)
        except ValueError:
            return []
        return [str(item) for item in value] if isinstance(value, list) else []


class FileVersion(Base, TimestampMixin):
    """A superseded copy of a file's contents (current bytes live on the file)."""

    __tablename__ = "file_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(200), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    replaced_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (UniqueConstraint("file_id", "version", name="uq_file_version"),)


class FileShare(Base, TimestampMixin, CreatedByMixin):
    """A share link for one file or one folder (optionally time limited)."""

    __tablename__ = "file_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    folder_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downloads: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
