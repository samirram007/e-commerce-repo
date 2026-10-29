"""payment gateway configs + payment record mode

Revision ID: b3f7d21a9c04
Revises: a7c3e91f5d20
Create Date: 2026-10-27 09:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b3f7d21a9c04'
down_revision = 'a7c3e91f5d20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'payment_gateway_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('mode', sa.String(length=4), nullable=False),
        sa.Column('display_name', sa.String(length=80), nullable=True),
        sa.Column('test_public_key', sa.String(length=255), nullable=True),
        sa.Column('live_public_key', sa.String(length=255), nullable=True),
        sa.Column('test_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('live_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('test_webhook_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('live_webhook_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('supported_methods', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_gateway_configs')),
        sa.UniqueConstraint('company_id', 'provider', name='uq_payment_gateway_configs_company_provider'),
    )
    with op.batch_alter_table('payment_gateway_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payment_gateway_configs_company_id'), ['company_id'], unique=False)

    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode', sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column('charge_ref', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.drop_column('charge_ref')
        batch_op.drop_column('mode')

    with op.batch_alter_table('payment_gateway_configs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payment_gateway_configs_company_id'))

    op.drop_table('payment_gateway_configs')