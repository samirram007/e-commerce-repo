"""merge storefront content branch with hsn/sac codes

Revision ID: 4f2d81319499
Revises: a7c3e91f5d20, b7f3a91c4e20
Create Date: 2026-10-26 21:09:42.394058
"""
import sqlalchemy as sa
from alembic import op

revision = '4f2d81319499'
down_revision = ('a7c3e91f5d20', 'b7f3a91c4e20')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
