"""File library routes (ERP): folders, files, versions, share links and trash.

The library is a folder tree over `StoredFile`. Folders may carry an access
rule (a permission and/or role names); restricted folders hide their contents
and every file in them is refused, while admins always see everything. Deleting
is soft by default — files go to the trash and bytes stay on disk — and only
`/purge` (admin) removes contents for real.

Public share links live under `/files/shared/...`, which never requires a
bearer token: the token in the URL is the whole capability.
"""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import (
    P_FILES_DELETE,
    P_FILES_MANAGE,
    P_FILES_UPLOAD,
    P_FILES_VIEW,
)
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.files import service as svc
from app.modules.files.models import FileFolder, FileShare
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/files")

MAX_PAGE = 500


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    required_permission: str | None = Field(default=None, max_length=64)
    role_names: list[str] = Field(default_factory=list)
    accepts_shopper_uploads: bool = False


class FolderUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    parent_id: str | None = None
    required_permission: str | None = Field(default=None, max_length=64)
    role_names: list[str] | None = None
    accepts_shopper_uploads: bool | None = None
    move: bool = False


class FileUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    folder_id: str | None = None
    visibility: str | None = None
    move: bool = False


class BulkIn(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=200)
    action: str = Field(description="trash, restore, move or purge")
    folder_id: str | None = None


class ShareIn(BaseModel):
    file_id: str | None = None
    folder_id: str | None = None
    expires_in_days: int | None = Field(default=None, ge=0, le=3650)
    note: str | None = Field(default=None, max_length=200)


def _folder_row(session: Session, ctx: CompanyCtx, folder_id: str, *, include_trashed: bool = False) -> FileFolder:
    return svc.get_folder(session, ctx.company_id, folder_id, include_trashed=include_trashed)


def _folder_ref(session: Session, record) -> dict | None:
    """Breadcrumb trail of a folder, root first."""
    if not record:
        return None
    return {"id": record.id, "name": record.name, "path": record.path}


def _breadcrumbs(session: Session, ctx: CompanyCtx, folder: FileFolder | None) -> list[dict]:
    trail: list[dict] = []
    current = folder
    while current is not None:
        trail.append(_folder_ref(session, current))
        current = session.get(FileFolder, current.parent_id) if current.parent_id else None
    return list(reversed(trail))


def _share_target(session: Session, share: FileShare) -> str | None:
    from app.shared.files import StoredFile

    if share.file_id:
        record = session.get(StoredFile, share.file_id)
        return record.original_name if record is not None else None
    folder = session.get(FileFolder, share.folder_id) if share.folder_id else None
    return folder.name if folder is not None else None


# ---- folders ----
@router.get("/folders")
def list_folders(
    include_trashed: bool = False,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    """The folder tree the caller may see, with file/subfolder counts."""
    return {"items": svc.folder_tree(session, ctx, include_trashed=include_trashed)}


@router.post("/folders", status_code=201)
def create_folder(
    payload: FolderIn,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    folder = svc.create_folder(
        session,
        ctx,
        name=payload.name,
        parent_id=payload.parent_id,
        required_permission=payload.required_permission,
        role_names=payload.role_names,
        accepts_shopper_uploads=payload.accepts_shopper_uploads,
    )
    log_action(
        session, action="file.folder.created", entity_type="file_folder", entity_id=folder.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"name": folder.name, "path": folder.path},
    )
    return svc.folder_out(folder)


@router.get("/folders/{folder_id}")
def get_folder(
    folder_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    folder = _folder_row(session, ctx, folder_id)
    svc.assert_folder_access(ctx, folder)
    files, subfolders = svc.folder_counts(session, folder)
    return {**svc.folder_out(folder), "files": files, "subfolders": subfolders}


@router.patch("/folders/{folder_id}")
def update_folder(
    folder_id: str,
    payload: FolderUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    """Rename, move or re-scope a folder (its descendants follow)."""
    folder = _folder_row(session, ctx, folder_id)
    data = payload.model_dump()
    updated = svc.update_folder(
        session,
        ctx,
        folder,
        name=data["name"],
        parent_id=data["parent_id"],
        required_permission=data["required_permission"],
        role_names=data["role_names"],
        accepts_shopper_uploads=data["accepts_shopper_uploads"],
        move=bool(data["move"]),
    )
    log_action(
        session, action="file.folder.updated", entity_type="file_folder", entity_id=folder.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"name": updated.name, "path": updated.path, "restricted": bool(updated.required_permission or updated.roles)},
    )
    return svc.folder_out(updated)


@router.delete("/folders/{folder_id}")
def trash_folder(
    folder_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    folder = _folder_row(session, ctx, folder_id)
    result = svc.trash_folder(session, ctx, folder)
    log_action(
        session, action="file.folder.trashed", entity_type="file_folder", entity_id=folder.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data=result,
    )
    return result


@router.post("/folders/{folder_id}/restore")
def restore_folder(
    folder_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    folder = _folder_row(session, ctx, folder_id, include_trashed=True)
    svc.restore_folder(session, ctx, folder)
    log_action(
        session, action="file.folder.restored", entity_type="file_folder", entity_id=folder.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return svc.folder_out(folder)


@router.delete("/folders/{folder_id}/purge")
def purge_folder(
    folder_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_DELETE)),
    session: Session = Depends(get_db),
):
    """Permanently delete a folder, its subfolders and every file inside."""
    folder = _folder_row(session, ctx, folder_id, include_trashed=True)
    if folder.deleted_at is None:
        raise BusinessRuleError("FOLDER_NOT_TRASHED", "Move the folder to the trash first")
    name = folder.name
    result = svc.purge_folder(session, ctx, folder)
    log_action(
        session, action="file.folder.purged", entity_type="file_folder", entity_id=folder_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data={"name": name, **result},
    )
    return result


# ---- share links (declare before /{file_id}) ----
@router.get("/shares")
def list_shares(
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    return {
        "items": [
            svc.share_out(share, target_name=_share_target(session, share))
            for share in svc.list_shares(session, ctx)
        ]
    }


@router.post("/shares", status_code=201)
def create_share(
    payload: ShareIn,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    """Mint a public link for one file or one folder, optionally time limited."""
    share = svc.create_share(
        session,
        ctx,
        file_id=payload.file_id,
        folder_id=payload.folder_id,
        expires_in_days=payload.expires_in_days,
        note=payload.note,
    )
    log_action(
        session, action="file.share.created", entity_type="file_share", entity_id=share.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"file_id": share.file_id, "folder_id": share.folder_id},
    )
    return svc.share_out(share, target_name=_share_target(session, share))


@router.delete("/shares/{share_id}")
def revoke_share(
    share_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    share = svc.revoke_share(session, ctx, share_id)
    log_action(
        session, action="file.share.revoked", entity_type="file_share", entity_id=share.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return svc.share_out(share, target_name=_share_target(session, share))


# ---- public share links (no auth: the token is the capability) ----
@router.get("/shared/{token}")
def open_share(token: str, session: Session = Depends(get_db)):
    """What a share link exposes: the folder listing, or the single file."""
    share, folder, files = svc.resolve_share(session, token)
    return {
        "token": share.token,
        "folder": _folder_ref(session, folder),
        "files": [
            {
                "id": record.id,
                "name": record.original_name,
                "content_type": record.content_type,
                "size_bytes": record.size_bytes,
                "download_url": f"/api/v1/files/shared/{share.token}/download/{record.id}",
            }
            for record in files
        ],
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
    }


@router.get("/shared/{token}/download/{file_id}")
def download_shared(
    token: str,
    file_id: str,
    download: bool = True,
    session: Session = Depends(get_db),
):
    share, _folder, files = svc.resolve_share(session, token)
    record = next((row for row in files if row.id == file_id), None)
    if record is None:
        raise NotFoundError("File")
    path, name, content_type = svc.bytes_of(session, record)
    share.downloads += 1
    return FileResponse(
        path=path,
        media_type=content_type,
        filename=name if download else None,
    )


# ---- trash listing (declare before /{file_id}) ----
@router.get("/trash")
def list_trash(
    search: str | None = None,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    rows = svc.list_files(session, ctx, search=search, trashed=True)
    return {"items": [svc.file_out(session, row) for row in rows]}


# ---- files ----
@router.get("")
def list_files(
    folder_id: str | None = None,
    search: str | None = None,
    include_subfolders: bool = False,
    purpose: str | None = None,
    limit: int = 200,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    """Files in a folder (or across everything the caller may see)."""
    folder = _folder_row(session, ctx, folder_id) if folder_id else None
    if folder is not None:
        svc.assert_folder_access(ctx, folder)
    rows = svc.list_files(
        session,
        ctx,
        folder_id=folder_id,
        search=search,
        include_subfolders=include_subfolders,
        purpose=purpose,
        limit=min(max(limit, 1), MAX_PAGE),
    )
    return {
        "items": [svc.file_out(session, row, folder=folder if row.folder_id == folder_id else None) for row in rows],
        "folder": svc.folder_out(folder) if folder is not None else None,
        "breadcrumbs": _breadcrumbs(session, ctx, folder),
        "subfolders": [
            svc.folder_out(row)
            for row in svc.visible_folders(session, ctx)
            if row.parent_id == (folder.id if folder is not None else None)
        ],
    }


@router.post("/upload", status_code=201)
def upload_file(
    file: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    visibility: str = Form(default="private"),
    purpose: str = Form(default="document"),
    ctx: CompanyCtx = Depends(guard(P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    record = svc.upload(session, ctx, file, folder_id=folder_id, visibility=visibility, purpose=purpose)
    log_action(
        session, action="file.uploaded", entity_type="stored_file", entity_id=record.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"name": record.original_name, "folder_id": record.folder_id, "visibility": visibility},
    )
    return svc.file_out(session, record)


@router.post("/bulk")
def bulk_action(
    payload: BulkIn,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    """Trash, restore, move or purge a selection in one call."""
    action = payload.action
    if action not in {"trash", "restore", "move", "purge"}:
        raise BusinessRuleError("BAD_ACTION", "action must be trash, restore, move or purge")
    if action == "purge" and "files.delete" not in ctx.permissions and not ctx.is_company_admin:
        raise BusinessRuleError("BAD_ACTION", "Purging requires the files.delete permission")
    changed = 0
    for file_id in payload.ids:
        record = svc.get_file(session, ctx.company_id, file_id, include_trashed=action in {"restore", "purge"})
        if action == "trash":
            svc.trash_file(session, ctx, record)
        elif action == "restore":
            svc.restore_file(session, ctx, record)
        elif action == "purge":
            svc.purge_file(session, ctx, record)
        else:
            svc.update_file(session, ctx, record, folder_id=payload.folder_id, move=True)
        changed += 1
    log_action(
        session, action=f"file.bulk.{action}", entity_type="stored_file", entity_id=None,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"count": changed, "folder_id": payload.folder_id},
    )
    return {"action": action, "changed": changed}


@router.get("/{file_id}")
def get_file(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id)
    svc.assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    return {**svc.file_out(session, record), "versions": svc.list_versions(session, record)}


@router.patch("/{file_id}")
def update_file(
    file_id: str,
    payload: FileUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    """Rename, move or change the visibility of one file."""
    record = svc.get_file(session, ctx.company_id, file_id)
    data = payload.model_dump()
    updated = svc.update_file(
        session,
        ctx,
        record,
        name=data["name"],
        folder_id=data["folder_id"],
        visibility=data["visibility"],
        move=bool(data["move"]),
    )
    log_action(
        session, action="file.updated", entity_type="stored_file", entity_id=record.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"name": updated.original_name, "folder_id": updated.folder_id, "visibility": updated.visibility},
    )
    return svc.file_out(session, updated)


@router.delete("/{file_id}")
def trash_file(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id)
    svc.trash_file(session, ctx, record)
    log_action(
        session, action="file.trashed", entity_type="stored_file", entity_id=record.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        before_data={"name": record.original_name},
    )
    return svc.file_out(session, record)


@router.post("/{file_id}/restore")
def restore_file(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_MANAGE)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id, include_trashed=True)
    svc.restore_file(session, ctx, record)
    log_action(
        session, action="file.restored", entity_type="stored_file", entity_id=record.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return svc.file_out(session, record)


@router.delete("/{file_id}/purge")
def purge_file(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_DELETE)),
    session: Session = Depends(get_db),
):
    """Delete one file (and its versions) permanently."""
    record = svc.get_file(session, ctx.company_id, file_id, include_trashed=True)
    name = record.original_name
    svc.purge_file(session, ctx, record)
    log_action(
        session, action="file.purged", entity_type="stored_file", entity_id=file_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data={"name": name},
    )
    return {"deleted": file_id}


@router.post("/{file_id}/contents")
def replace_contents(
    file_id: str,
    file: UploadFile = File(...),
    ctx: CompanyCtx = Depends(guard(P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    """Upload new contents for a file; the previous bytes stay as a version."""
    record = svc.get_file(session, ctx.company_id, file_id)
    updated = svc.replace_contents(session, ctx, record, file)
    log_action(
        session, action="file.version.created", entity_type="stored_file", entity_id=record.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"size_bytes": updated.size_bytes, "versions": len(svc.list_versions(session, updated))},
    )
    return svc.file_out(session, updated)


@router.get("/{file_id}/versions")
def list_versions(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id)
    svc.assert_folder_access(ctx, session.get(FileFolder, record.folder_id) if record.folder_id else None)
    return {"file_id": record.id, "items": svc.list_versions(session, record)}


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    download: bool = False,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id)
    path, name, content_type = svc.open_contents(session, ctx, record)
    return FileResponse(path=path, media_type=content_type, filename=name if download else None)


@router.get("/{file_id}/versions/{version_id}/download")
def download_version(
    file_id: str,
    version_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    record = svc.get_file(session, ctx.company_id, file_id)
    path, name, content_type = svc.open_contents(session, ctx, record, version_id=version_id)
    return FileResponse(path=path, media_type=content_type, filename=name)


@router.get("/{file_id}/usage")
def file_usage(
    file_id: str,
    ctx: CompanyCtx = Depends(guard(P_FILES_VIEW)),
    session: Session = Depends(get_db),
):
    """Where a file is referenced, so deleting it is an informed decision."""
    from app.modules.catalog.models import Category, Product, ProductImage
    from app.modules.storefront.models import StorefrontHeroSlide, StorefrontSettings

    record = svc.get_file(session, ctx.company_id, file_id)
    used: list[dict] = []
    product = session.scalar(
        select(Product).where(Product.company_id == ctx.company_id, Product.image_file_id == file_id)
    )
    if product is not None:
        used.append({"kind": "product", "label": product.name, "id": product.id})
    image = session.scalar(
        select(ProductImage).where(ProductImage.file_id == file_id)
    )
    if image is not None:
        used.append({"kind": "product_image", "label": image.alt or "Gallery image", "id": image.id})
    category = session.scalar(
        select(Category).where(Category.company_id == ctx.company_id, Category.image_file_id == file_id)
    )
    if category is not None:
        used.append({"kind": "category", "label": category.name, "id": category.id})
    slide = session.scalar(
        select(StorefrontHeroSlide).where(
            StorefrontHeroSlide.company_id == ctx.company_id, StorefrontHeroSlide.image_file_id == file_id
        )
    )
    if slide is not None:
        used.append({"kind": "hero_slide", "label": slide.title, "id": slide.id})
    settings_row = session.scalar(
        select(StorefrontSettings).where(
            StorefrontSettings.company_id == ctx.company_id, StorefrontSettings.map_image_file_id == file_id
        )
    )
    if settings_row is not None:
        used.append({"kind": "storefront_map", "label": "Contact map", "id": settings_row.id})
    if record.order_id:
        used.append({"kind": "order", "label": f"Order {record.order_id}", "id": record.order_id})
    return {"file_id": record.id, "used": used, "count": len(used)}
