"""Sequential document numbering scoped by company/document-type/fiscal year.

Uses SELECT ... FOR UPDATE (via SQLAlchemy `with_for_update`, no-op on SQLite
where the transaction writer lock gives equivalent safety) to make allocation
safe under concurrency on PostgreSQL.
"""
from sqlalchemy import Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.exceptions import ConflictError
from app.core.security import new_id
from app.db.base import Base, TimestampMixin

DOC_TYPES = [
    "sales_order", "invoice", "credit_note", "purchase_order", "vendor_bill",
    "goods_receipt", "sales_return", "purchase_return", "receipt", "payment",
    "journal_entry", "shipment", "stock_adjustment", "refund",
]

_NUM_REJECTED_DOC_TYPES = "INVALID_DOC_TYPE"


class DocumentSequence(Base, TimestampMixin):
    __tablename__ = "document_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fiscal_year_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    # seq_key = f"{company_id}/{doc_type}/{fiscal_year_id or 'ALL'}"
    seq_key: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (UniqueConstraint("seq_key", name="uq_document_sequences_seq_key"),)


def allocate_number(
    session,
    company_id: str,
    doc_type: str,
    fiscal_year_id: str | None = None,
    *,
    prefix: str = "",
    padding: int = 6,
) -> str:
    """Atomically allocate the next document number and return it.

    Must be called within the active use-case transaction (UoW owns commit) so
    the row lock lasts until commit and concurrent requests serialize on
    PostgreSQL instead of allocating duplicates.
    """
    if doc_type not in DOC_TYPES:
        raise ConflictError(_NUM_REJECTED_DOC_TYPES, f"Unknown document type '{doc_type}'")
    seq_key = f"{company_id}/{doc_type}/{fiscal_year_id or 'ALL'}"
    seq = session.execute(
        select(DocumentSequence).where(DocumentSequence.seq_key == seq_key).with_for_update()
    ).scalar_one_or_none()
    if seq is None:
        seq = DocumentSequence(
            company_id=company_id,
            doc_type=doc_type,
            fiscal_year_id=fiscal_year_id,
            prefix=prefix,
            next_number=2,
            padding=padding,
            seq_key=seq_key,
        )
        session.add(seq)
        number = 1
    else:
        number = seq.next_number
        seq.next_number = number + 1
    return f"{prefix}{str(number).zfill(padding)}"
