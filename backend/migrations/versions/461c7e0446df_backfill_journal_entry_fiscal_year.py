"""backfill journal entry fiscal year

Revision ID: 461c7e0446df
Revises: 0bedd21c3d40
Create Date: 2026-10-16 19:58:34.211108
"""
import sqlalchemy as sa
from alembic import op

revision = '461c7e0446df'
down_revision = '0bedd21c3d40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Data-only backfill: entries posted before `post_journal_entry` populated
    # `fiscal_year_id` are NULL. Match each such entry to the fiscal year whose
    # date range contains its entry_date — the same rule as `resolve_fiscal_year`.
    op.execute(
        sa.text(
            """
            UPDATE journal_entries
            SET fiscal_year_id = (
                SELECT fy.id
                FROM fiscal_years AS fy
                WHERE fy.company_id = journal_entries.company_id
                  AND fy.start_date <= journal_entries.entry_date
                  AND fy.end_date >= journal_entries.entry_date
                ORDER BY fy.start_date
                LIMIT 1
            )
            WHERE fiscal_year_id IS NULL
            """
        )
    )


def downgrade() -> None:
    # Data-only migration: clearing the snapshot restores the prior state.
    op.execute(sa.text("UPDATE journal_entries SET fiscal_year_id = NULL"))
