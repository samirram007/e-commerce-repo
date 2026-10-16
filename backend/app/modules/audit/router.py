"""Audit HTTP routes — read-only, permission-gated."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSION_VIEW_AUDIT_LOG
from app.db.unit_of_work import get_db
from app.modules.audit.service import list_audit
from app.modules.identity.dependencies import CompanyCtx, guard

router = APIRouter(prefix="/audit")


class AuditOut(BaseModel):
    id: str
    company_id: str | None
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before_data: str | None
    after_data: str | None
    created_at: str


@router.get("", response_model=list[AuditOut])
def read_audit(
    limit: int = 100,
    offset: int = 0,
    ctx: CompanyCtx = Depends(guard(PERMISSION_VIEW_AUDIT_LOG)),
    session: Session = Depends(get_db),
):
    rows = list_audit(
        session,
        company_id=ctx.company_id,
        limit=limit,
        offset=offset,
    )
    return [
        AuditOut(
            id=r.id,
            company_id=r.company_id,
            actor_user_id=r.actor_user_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            before_data=r.before_data,
            after_data=r.after_data,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
