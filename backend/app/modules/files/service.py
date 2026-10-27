"""File library service: a folder tree over `StoredFile` plus the operations the
Files screen needs.

Access is per folder: a folder with no `required_permission` and no roles is
open to anyone holding the files permissions, while a restricted folder (and
everything under it, including its files) needs the permission or one of the
roles. Company and platform admins always pass.

Files are never hard-deleted by the UI: trashing sets `deleted_at` (contents
stay on disk so a restore is lossless) and only `purge` removes bytes. Replacing
a file's contents first snapshots the previous bytes as a `FileVersion`.
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.modules.files.models import SYSTEM_FOLDERS, FileFolder, FileShare, FileVersion
from app.shared.files import (
    ALLOWED_CONTENT_TYPES,
    IMAGE_CONTENT_TYPES,
    StoredFile,
    _media_root,
    discard_contents,
    save_file,
    store_upload,
)

#: Purpose → system folder, so uploads made by other screens land organised.
PURPOSE_FOLDERS = {
    "product_image": "product_images",
    "category_image": "storefront_media",
    "hero_image": "storefront_media",
    "contact_map": "storefront_media",
    "payroll": "payroll_documents",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Compare stored timestamps safely (SQLite hands back naive datetimes)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _is_admin(ctx) -> bool:
    return bool(ctx.user.is_platform_admin or ctx.is_company_admin or "*" in ctx.permissions)


# ---- folders ----
def get_folder(session: Session, company_id: str, folder_id: str, *, include_trashed: bool = False) -> FileFolder:
    row = session.get(FileFolder, folder_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Folder")
    if row.deleted_at is not None and not include_trashed:
        raise NotFoundError("Folder")
    return row


def can_access(ctx, folder: FileFolder | None) -> bool:
    """Whether the caller may see this folder (and therefore the files in it)."""
    if folder is None:
        return True  # the library root / unfiled uploads
    if _is_admin(ctx):
        return True
    if not folder.required_permission and not folder.roles:
        return True
    if folder.required_permission and folder.required_permission in ctx.permissions:
        return True
    return bool(set(folder.roles) & ctx.roles)


def assert_folder_access(ctx, folder: FileFolder | None) -> None:
    if not can_access(ctx, folder):
        raise ForbiddenError(f"'{folder.name}' is restricted to other roles")


def visible_folders(session: Session, ctx, *, include_trashed: bool = False) -> list[FileFolder]:
    query = select(FileFolder).where(FileFolder.company_id == ctx.company_id)
    if not include_trashed:
        query = query.where(FileFolder.deleted_at.is_(None))
    rows = list(session.execute(query.order_by(FileFolder.path, FileFolder.name)).scalars())
    return [row for row in rows if can_access(ctx, row)]


def _children(session: Session, folder: FileFolder) -> list[FileFolder]:
    return list(
        session.execute(
            select(FileFolder).where(
                FileFolder.company_id == folder.company_id, FileFolder.parent_id == folder.id
            )
        ).scalars()
    )


def descendants(session: Session, folder: FileFolder) -> list[FileFolder]:
    """Every folder below this one (breadth first, used by moves and trashing)."""
    out: list[FileFolder] = []
    queue = [folder]
    while queue:
        current = queue.pop(0)
        children = _children(session, current)
        out.extend(children)
        queue.extend(children)
    return out


def _folder_path(session: Session, folder: FileFolder | None, name: str) -> str:
    if folder is None:
        return f"/{name}"
    return f"{folder.path.rstrip('/')}/{name}"


def folder_counts(session: Session, folder: FileFolder) -> tuple[int, int]:
    """(files directly inside, subfolders) — what the tree shows next to a name."""
    files = session.execute(
        select(func.count())
        .select_from(StoredFile)
        .where(
            StoredFile.folder_id == folder.id,
            StoredFile.company_id == folder.company_id,
            StoredFile.deleted_at.is_(None),
        )
    ).scalar_one()
    return int(files), len(_children(session, folder))


def folder_tree(session: Session, ctx, *, include_trashed: bool = False) -> list[dict]:
    """Visible folders with their counts, ready for the sidebar tree."""
    ensure_system_folders(session, ctx)
    out: list[dict] = []
    for folder in visible_folders(session, ctx, include_trashed=include_trashed):
        files, subfolders = folder_counts(session, folder)
        out.append({**folder_out(folder), "files": files, "subfolders": subfolders})
    return out


def folder_out(folder: FileFolder) -> dict:
    return {
        "id": folder.id,
        "parent_id": folder.parent_id,
        "name": folder.name,
        "path": folder.path,
        "system_key": folder.system_key,
        "required_permission": folder.required_permission,
        "role_names": folder.roles,
        "accepts_shopper_uploads": folder.accepts_shopper_uploads,
        "restricted": bool(folder.required_permission or folder.roles),
        "deleted_at": folder.deleted_at.isoformat() if folder.deleted_at else None,
    }


def system_folder(
    session: Session, *, company_id: str, key: str, actor_user_id: str | None = None
) -> FileFolder:
    """Get (or create) one of the application's own folders."""
    row = session.scalar(
        select(FileFolder).where(
            FileFolder.company_id == company_id, FileFolder.system_key == key
        )
    )
    if row is not None:
        return row
    name = SYSTEM_FOLDERS.get(key, key.replace("_", " ").title())
    # Adopt a root folder the company already made with the same name, so the
    # unique (company, parent, name) constraint cannot be violated.
    sibling = session.scalar(
        select(FileFolder).where(
            FileFolder.company_id == company_id,
            FileFolder.parent_id.is_(None),
            func.lower(FileFolder.name) == name.lower(),
        )
    )
    if sibling is not None:
        sibling.system_key = key
        if key == "shopper_uploads":
            sibling.accepts_shopper_uploads = True
        session.flush()
        return sibling
    row = FileFolder(
        company_id=company_id,
        name=name,
        path=f"/{name}",
        system_key=key,
        accepts_shopper_uploads=key == "shopper_uploads",
        created_by=actor_user_id,
    )
    session.add(row)
    session.flush()
    return row


def ensure_system_folders(session: Session, ctx) -> list[FileFolder]:
    """Create the application's own folders so the library always shows them.

    Called when the tree is listed: the admin then sees (and can toggle) the
    "Customer uploads" inbox instead of it appearing only after the first
    shopper upload.
    """
    return [
        system_folder(session, company_id=ctx.company_id, key=key, actor_user_id=ctx.user.id)
        for key in SYSTEM_FOLDERS
    ]


def file_upload(
    session: Session,
    *,
    company_id: str,
    record: StoredFile,
    actor_user_id: str | None = None,
) -> StoredFile:
    """File an upload into the system folder for its purpose (called on save).

    Uploads made by other screens (product images, storefront media) show up in
    the library already organised instead of loose at the root.
    """
    if record.folder_id:
        return record
    key = PURPOSE_FOLDERS.get(record.purpose, "general")
    folder = system_folder(session, company_id=company_id, key=key, actor_user_id=actor_user_id)
    record.folder_id = folder.id
    session.flush()
    return record


def create_folder(
    session: Session,
    ctx,
    *,
    name: str,
    parent_id: str | None = None,
    required_permission: str | None = None,
    role_names: list[str] | None = None,
    accepts_shopper_uploads: bool = False,
) -> FileFolder:
    clean = (name or "").strip()
    if not clean:
        raise BusinessRuleError("BAD_FOLDER_NAME", "A folder needs a name")
    parent = get_folder(session, ctx.company_id, parent_id) if parent_id else None
    if parent is not None:
        assert_folder_access(ctx, parent)
    exists = session.scalar(
        select(FileFolder.id).where(
            FileFolder.company_id == ctx.company_id,
            FileFolder.parent_id == (parent.id if parent else None),
            func.lower(FileFolder.name) == clean.lower(),
            FileFolder.deleted_at.is_(None),
        )
    )
    if exists:
        raise ConflictError("FOLDER_EXISTS", f"'{clean}' already exists here")
    folder = FileFolder(
        company_id=ctx.company_id,
        parent_id=parent.id if parent else None,
        name=clean,
        path=_folder_path(session, parent, clean),
        required_permission=(required_permission or "").strip() or None,
        role_names=json.dumps(sorted(set(role_names or []))) if role_names else None,
        accepts_shopper_uploads=accepts_shopper_uploads,
        created_by=ctx.user.id,
    )
    session.add(folder)
    session.flush()
    return folder


def update_folder(
    session: Session,
    ctx,
    folder: FileFolder,
    *,
    name: str | None = None,
    parent_id: str | None = None,
    required_permission: str | None = None,
    role_names: list[str] | None = None,
    accepts_shopper_uploads: bool | None = None,
    move: bool = False,
) -> FileFolder:
    """Rename, move or re-scope a folder (paths of the subtree follow)."""
    assert_folder_access(ctx, folder)
    if name is not None and name.strip():
        folder.name = name.strip()
    if move:
        parent = get_folder(session, ctx.company_id, parent_id) if parent_id else None
        if parent is not None:
            assert_folder_access(ctx, parent)
            if parent.id == folder.id or parent.id in {row.id for row in descendants(session, folder)}:
                raise BusinessRuleError("BAD_FOLDER_MOVE", "A folder cannot be moved inside itself")
        folder.parent_id = parent.id if parent else None
        folder.path = _folder_path(session, parent, folder.name)
    if folder.parent_id is None and name is not None:
        folder.path = f"/{folder.name}"
    elif not move:
        parent = session.get(FileFolder, folder.parent_id) if folder.parent_id else None
        folder.path = _folder_path(session, parent, folder.name)
    if required_permission is not None:
        folder.required_permission = required_permission.strip() or None
    if role_names is not None:
        folder.role_names = json.dumps(sorted(set(role_names))) if role_names else None
    if accepts_shopper_uploads is not None:
        folder.accepts_shopper_uploads = accepts_shopper_uploads
    session.flush()
    # keep descendant paths (and their visibility) in step
    for child in descendants(session, folder):
        child.path = _folder_path(session, session.get(FileFolder, child.parent_id), child.name)
    session.flush()
    return folder


def folder_files(session: Session, folder: FileFolder, *, include_trashed: bool = False) -> list[StoredFile]:
    query = select(StoredFile).where(StoredFile.folder_id == folder.id)
    if not include_trashed:
        query = query.where(StoredFile.deleted_at.is_(None))
    return list(session.execute(query).scalars())


def trash_folder(session: Session, ctx, folder: FileFolder) -> dict:
    """Move a folder, its subfolders and their files to the trash."""
    assert_folder_access(ctx, folder)
    stamp = _now()
    trashed_files = 0
    for row in [folder, *descendants(session, folder)]:
        for record in folder_files(session, row):
            record.deleted_at = stamp
            trashed_files += 1
        row.deleted_at = stamp
    session.flush()
    return {"folder_id": folder.id, "files_trashed": trashed_files}


def restore_folder(session: Session, ctx, folder: FileFolder) -> FileFolder:
    assert_folder_access(ctx, folder)
    for row in [folder, *descendants(session, folder)]:
        row.deleted_at = None
        for record in folder_files(session, row, include_trashed=True):
            record.deleted_at = None
    session.flush()
    return folder


def purge_folder(session: Session, ctx, folder: FileFolder) -> dict:
    """Permanently delete a trashed folder (contents included)."""
    if not _is_admin(ctx):
        raise ForbiddenError("Only an admin can delete a folder permanently")
    rows = [folder, *descendants(session, folder)]
    removed = 0
    for row in rows:
        for record in folder_files(session, row, include_trashed=True):
            _purge_file(session, record)
            removed += 1
        session.delete(row)
    session.flush()
    return {"deleted": folder.id, "files_removed": removed}


# ---- files ----
def get_file(session: Session, company_id: str, file_id: str, *, include_trashed: bool = False) -> StoredFile:
    record = session.get(StoredFile, file_id)
    if record is None or (record.company_id not in (None, company_id)):
        raise NotFoundError("File")
    if record.deleted_at is not None and not include_trashed:
        raise NotFoundError("File")
    return record


def file_out(session: Session, record: StoredFile, *, folder: FileFolder | None = None) -> dict:
    folder = folder if folder is not None else (
        session.get(FileFolder, record.folder_id) if record.folder_id else None
    )
    version_count = session.execute(
        select(func.count()).select_from(FileVersion).where(FileVersion.file_id == record.id)
    ).scalar_one()
    return {
        "id": record.id,
        "name": record.original_name,
        "content_type": record.content_type,
        "size_bytes": record.size_bytes,
        "visibility": record.visibility,
        "purpose": record.purpose,
        "folder_id": record.folder_id,
        "folder_path": folder.path if folder is not None else None,
        "uploaded_via": record.uploaded_via,
        "order_id": record.order_id,
        "owner_key": record.owner_key,
        "version_count": int(version_count),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
        "download_url": f"/api/v1/files/{record.id}/download",
    }


def list_files(
    session: Session,
    ctx,
    *,
    folder_id: str | None = None,
    search: str | None = None,
    trashed: bool = False,
    include_subfolders: bool = False,
    purpose: str | None = None,
    limit: int = 300,
) -> list[StoredFile]:
    """Files in a folder (or across the whole tree, permission filtered)."""
    query = select(StoredFile).where(StoredFile.company_id == ctx.company_id)
    query = query.where(
        StoredFile.deleted_at.is_not(None) if trashed else StoredFile.deleted_at.is_(None)
    )
    if purpose:
        query = query.where(StoredFile.purpose == purpose)
    if folder_id:
        folder = get_folder(session, ctx.company_id, folder_id, include_trashed=trashed)
        assert_folder_access(ctx, folder)
        if include_subfolders:
            ids = [folder.id, *[row.id for row in descendants(session, folder)]]
            query = query.where(StoredFile.folder_id.in_(ids))
        else:
            query = query.where(StoredFile.folder_id == folder.id)
    else:
        allowed = {row.id for row in visible_folders(session, ctx, include_trashed=trashed)}
        query = query.where(
            or_(StoredFile.folder_id.is_(None), StoredFile.folder_id.in_(allowed or [""]))
        )
    if search:
        query = query.where(StoredFile.original_name.ilike(f"%{search.strip()}%"))
    rows = list(session.execute(query.order_by(StoredFile.created_at.desc()).limit(limit)).scalars())
    return rows


def upload(
    session: Session,
    ctx,
    upload_file: UploadFile,
    *,
    folder_id: str | None = None,
    visibility: str = "private",
    purpose: str = "document",
    allowed_types: set[str] | None = None,
) -> StoredFile:
    folder = get_folder(session, ctx.company_id, folder_id) if folder_id else None
    if folder is not None:
        assert_folder_access(ctx, folder)
    return save_file(
        session,
        upload_file,
        company_id=ctx.company_id,
        purpose=purpose,
        created_by=ctx.user.id,
        allowed_types=allowed_types,
        visibility=visibility,
        folder_id=folder.id if folder else None,
    )


def update_file(
    session: Session,
    ctx,
    record: StoredFile,
    *,
    name: str | None = None,
    folder_id: str | None = None,
    visibility: str | None = None,
    move: bool = False,
) -> StoredFile:
    assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    if name is not None and name.strip():
        record.original_name = name.strip()[:255]
    if move:
        target = get_folder(session, ctx.company_id, folder_id) if folder_id else None
        if target is not None:
            assert_folder_access(ctx, target)
        record.folder_id = target.id if target else None
    if visibility is not None:
        if visibility not in {"private", "public"}:
            raise BusinessRuleError("BAD_FILE_VISIBILITY", "visibility must be 'private' or 'public'")
        record.visibility = visibility
    session.flush()
    return record


def replace_contents(session: Session, ctx, record: StoredFile, upload_file: UploadFile) -> StoredFile:
    """Replace a file's contents, keeping the previous bytes as a version."""
    assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    latest = session.execute(
        select(func.max(FileVersion.version)).where(FileVersion.file_id == record.id)
    ).scalar()
    stored = store_upload(upload_file, purpose=record.purpose)
    session.add(
        FileVersion(
            file_id=record.id,
            company_id=record.company_id or ctx.company_id,
            version=int(latest or 0) + 1,
            storage_key=record.storage_key,
            original_name=record.original_name,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            replaced_by=ctx.user.id,
        )
    )
    record.storage_key = stored["storage_key"]
    record.original_name = name_or(stored["original_name"], record.original_name)
    record.content_type = stored["content_type"]
    record.size_bytes = stored["size_bytes"]
    session.flush()
    return record


def name_or(candidate: str, fallback: str) -> str:
    return candidate or fallback


def list_versions(session: Session, record: StoredFile) -> list[dict]:
    rows = session.execute(
        select(FileVersion)
        .where(FileVersion.file_id == record.id)
        .order_by(FileVersion.version.desc())
    ).scalars()
    return [
        {
            "id": row.id,
            "version": row.version,
            "name": row.original_name,
            "size_bytes": row.size_bytes,
            "content_type": row.content_type,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "download_url": f"/api/v1/files/{record.id}/versions/{row.id}/download",
        }
        for row in rows
    ]


def bytes_of(
    session: Session, record: StoredFile, *, version_id: str | None = None
) -> tuple[Path, str, str]:
    """Resolve (path, filename, content type) for a file or one stored version.

    No authorization happens here: callers either asserted folder access (the
    library) or hold a share token (the public link).
    """
    if version_id:
        version = session.get(FileVersion, version_id)
        if version is None or version.file_id != record.id:
            raise NotFoundError("File version")
        storage_key = version.storage_key
        name, content_type = version.original_name, version.content_type
    else:
        storage_key, name, content_type = record.storage_key, record.original_name, record.content_type
    path = _media_root() / storage_key
    if not path.is_file():
        raise NotFoundError("File contents")
    return path, name, content_type


def open_contents(
    session: Session, ctx, record: StoredFile, *, version_id: str | None = None
) -> tuple[Path, str, str]:
    """Bytes for an authenticated download (folder access is enforced)."""
    if not version_id:
        assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    return bytes_of(session, record, version_id=version_id)


def trash_file(session: Session, ctx, record: StoredFile) -> StoredFile:
    assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    record.deleted_at = _now()
    session.flush()
    return record


def restore_file(session: Session, ctx, record: StoredFile) -> StoredFile:
    record.deleted_at = None
    session.flush()
    return record


def purge_file(session: Session, ctx, record: StoredFile) -> None:
    if not _is_admin(ctx):
        raise ForbiddenError("Only an admin can delete a file permanently")
    _purge_file(session, record)


def _purge_file(session: Session, record: StoredFile) -> None:
    for version in session.execute(
        select(FileVersion).where(FileVersion.file_id == record.id)
    ).scalars():
        discard_contents(version.storage_key)
        session.delete(version)
    discard_contents(record.storage_key)
    session.delete(record)
    session.flush()


# ---- share links ----
def create_share(
    session: Session,
    ctx,
    *,
    file_id: str | None = None,
    folder_id: str | None = None,
    expires_in_days: int | None = None,
    note: str | None = None,
) -> FileShare:
    """Create a public link for one file or folder (optionally time limited)."""
    if bool(file_id) == bool(folder_id):
        raise BusinessRuleError("BAD_SHARE_TARGET", "Share either one file or one folder")
    record = None
    folder = None
    if file_id:
        record = get_file(session, ctx.company_id, file_id)
        folder = session.get(FileFolder, record.folder_id) if record.folder_id else None
    else:
        folder = get_folder(session, ctx.company_id, folder_id)
    assert_folder_access(ctx, folder)
    expires_at = None
    if expires_in_days is not None:
        # 0 days means "expires now" — a link that is valid until this instant.
        expires_at = _now() + timedelta(days=int(expires_in_days))
    share = FileShare(
        company_id=ctx.company_id,
        file_id=record.id if record else None,
        folder_id=folder.id if folder else None,
        token=secrets.token_urlsafe(24),
        note=(note or "").strip()[:200] or None,
        expires_at=expires_at,
        created_by=ctx.user.id,
    )
    session.add(share)
    session.flush()
    return share


def share_out(share: FileShare, *, target_name: str | None = None) -> dict:
    return {
        "id": share.id,
        "token": share.token,
        "url": f"/api/v1/files/shared/{share.token}",
        "file_id": share.file_id,
        "folder_id": share.folder_id,
        "target": target_name,
        "note": share.note,
        "downloads": share.downloads,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


def list_shares(session: Session, ctx) -> list[FileShare]:
    return list(
        session.execute(
            select(FileShare)
            .where(FileShare.company_id == ctx.company_id)
            .order_by(FileShare.created_at.desc())
            .limit(200)
        ).scalars()
    )


def revoke_share(session: Session, ctx, share_id: str) -> FileShare:
    share = session.get(FileShare, share_id)
    if share is None or share.company_id != ctx.company_id:
        raise NotFoundError("Share link")
    share.revoked_at = _now()
    session.flush()
    return share


def resolve_share(session: Session, token: str) -> tuple[FileShare, FileFolder | None, list[StoredFile]]:
    """Look up a public link: the share, its folder (when shared) and its files.

    Expired or revoked links behave exactly like unknown ones, so a stale URL
    never reveals whether the file still exists.
    """
    share = session.scalar(select(FileShare).where(FileShare.token == token))
    if share is None or share.revoked_at is not None:
        raise NotFoundError("Share link")
    if share.expires_at is not None and _as_utc(share.expires_at) < _now():
        raise NotFoundError("Share link")
    if share.file_id:
        record = session.get(StoredFile, share.file_id)
        if record is None or record.deleted_at is not None:
            raise NotFoundError("File")
        return share, None, [record]
    folder = session.get(FileFolder, share.folder_id)
    if folder is None or folder.deleted_at is not None:
        raise NotFoundError("Folder")
    # A folder share grants its contents for as long as the link is live.
    return share, folder, folder_files(session, folder)


# ---- storefront (shopper) uploads ----
def shopper_upload(
    session: Session,
    *,
    company_id: str,
    owner: str,
    upload_file: UploadFile,
    order_id: str | None = None,
) -> StoredFile:
    """Attach a file from the storefront into the moderated customer inbox."""
    folder = session.scalar(
        select(FileFolder).where(
            FileFolder.company_id == company_id,
            FileFolder.system_key == "shopper_uploads",
            FileFolder.deleted_at.is_(None),
        )
    )
    if folder is None or not folder.accepts_shopper_uploads:
        raise BusinessRuleError(
            "UPLOADS_DISABLED", "This store does not accept customer uploads"
        )
    return save_file(
        session,
        upload_file,
        company_id=company_id,
        purpose="shopper_upload",
        allowed_types=IMAGE_CONTENT_TYPES | ALLOWED_CONTENT_TYPES,
        visibility="private",
        folder_id=folder.id,
        uploaded_via="storefront",
        owner_key=owner,
        order_id=order_id,
    )


def shopper_files(session: Session, company_id: str, owner: str) -> list[StoredFile]:
    return list(
        session.execute(
            select(StoredFile)
            .where(
                StoredFile.company_id == company_id,
                StoredFile.owner_key == owner,
                StoredFile.deleted_at.is_(None),
            )
            .order_by(StoredFile.created_at.desc())
        ).scalars()
    )
