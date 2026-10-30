"""merge heads: payment gateway configs, file library and main's storefront chain

Revision ID: c9e4a2f61b37
Revises: 7d72c5728a55, 8c1f4a7d2e90, b3f7d21a9c04
Create Date: 2026-10-29 22:00:00.000000

Also drops `payment_gateways` (main's superseded plaintext-credential table,
see a337a5b704e8) when a database still has it.
"""
import sqlalchemy as sa
from alembic import op

revision = 'c9e4a2f61b37'
down_revision = ('7d72c5728a55', '8c1f4a7d2e90', 'b3f7d21a9c04')
branch_labels = None
depends_on = None


def upgrade() -> None:
    if 'payment_gateways' in sa.inspect(op.get_bind()).get_table_names():
        with op.batch_alter_table('payment_gateways', schema=None) as batch_op:
            batch_op.drop_index('ix_payment_gateways_company_id', if_exists=True)
        op.drop_table('payment_gateways')


def downgrade() -> None:
    # The superseded table is not recreated; a337a5b704e8 is a no-op now.
    pass
