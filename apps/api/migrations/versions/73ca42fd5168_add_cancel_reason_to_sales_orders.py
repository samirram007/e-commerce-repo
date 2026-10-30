"""add cancel reason to sales orders

Revision ID: 73ca42fd5168
Revises: 3e6d1cbd15fb
Create Date: 2026-10-25 02:40:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = '73ca42fd5168'
down_revision = '3e6d1cbd15fb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('sales_orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cancel_reason', sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sales_orders', schema=None) as batch_op:
        batch_op.drop_column('cancel_reason')
