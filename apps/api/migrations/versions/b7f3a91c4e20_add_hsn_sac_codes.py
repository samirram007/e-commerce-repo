"""add hsn/sac codes to products and invoice lines

Revision ID: b7f3a91c4e20
Revises: 73ca42fd5168
Create Date: 2026-10-25 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b7f3a91c4e20'
down_revision = '73ca42fd5168'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hsn_sac', sa.String(length=12), nullable=True))
    with op.batch_alter_table('invoice_lines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hsn_sac_snapshot', sa.String(length=12), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('invoice_lines', schema=None) as batch_op:
        batch_op.drop_column('hsn_sac_snapshot')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('hsn_sac')
