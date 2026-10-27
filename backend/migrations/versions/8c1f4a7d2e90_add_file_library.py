"""add file library (folders, versions, shares, trash)

Revision ID: 8c1f4a7d2e90
Revises: 649d352f339d
Create Date: 2026-10-27 10:12:04.118302
"""
import sqlalchemy as sa
from alembic import op

revision = '8c1f4a7d2e90'
down_revision = '649d352f339d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'file_folders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('parent_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('path', sa.String(length=400), nullable=False),
        sa.Column('system_key', sa.String(length=32), nullable=True),
        sa.Column('required_permission', sa.String(length=64), nullable=True),
        sa.Column('role_names', sa.Text(), nullable=True),
        sa.Column('accepts_shopper_uploads', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_file_folders')),
        sa.UniqueConstraint('company_id', 'parent_id', 'name', name='uq_file_folder_name'),
    )
    with op.batch_alter_table('file_folders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_file_folders_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_folders_parent_id'), ['parent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_folders_system_key'), ['system_key'], unique=False)

    op.create_table(
        'file_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('file_id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=200), nullable=False),
        sa.Column('original_name', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('replaced_by', sa.String(length=36), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_file_versions')),
        sa.UniqueConstraint('file_id', 'version', name='uq_file_version'),
    )
    with op.batch_alter_table('file_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_file_versions_file_id'), ['file_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_versions_company_id'), ['company_id'], unique=False)

    op.create_table(
        'file_shares',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('file_id', sa.String(length=36), nullable=True),
        sa.Column('folder_id', sa.String(length=36), nullable=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('downloads', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_file_shares')),
    )
    with op.batch_alter_table('file_shares', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_file_shares_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_shares_file_id'), ['file_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_shares_folder_id'), ['folder_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_file_shares_token'), ['token'], unique=True)

    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.add_column(sa.Column('folder_id', sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column('uploaded_via', sa.String(length=16), nullable=False, server_default='erp')
        )
        batch_op.add_column(sa.Column('owner_key', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('order_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_files_folder_id'), ['folder_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_files_owner_key'), ['owner_key'], unique=False)
        batch_op.create_index(batch_op.f('ix_files_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_files_deleted_at'), ['deleted_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_files_deleted_at'))
        batch_op.drop_index(batch_op.f('ix_files_order_id'))
        batch_op.drop_index(batch_op.f('ix_files_owner_key'))
        batch_op.drop_index(batch_op.f('ix_files_folder_id'))
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('order_id')
        batch_op.drop_column('owner_key')
        batch_op.drop_column('uploaded_via')
        batch_op.drop_column('folder_id')

    with op.batch_alter_table('file_shares', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_file_shares_token'))
        batch_op.drop_index(batch_op.f('ix_file_shares_folder_id'))
        batch_op.drop_index(batch_op.f('ix_file_shares_file_id'))
        batch_op.drop_index(batch_op.f('ix_file_shares_company_id'))

    op.drop_table('file_shares')

    with op.batch_alter_table('file_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_file_versions_company_id'))
        batch_op.drop_index(batch_op.f('ix_file_versions_file_id'))

    op.drop_table('file_versions')

    with op.batch_alter_table('file_folders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_file_folders_system_key'))
        batch_op.drop_index(batch_op.f('ix_file_folders_parent_id'))
        batch_op.drop_index(batch_op.f('ix_file_folders_company_id'))

    op.drop_table('file_folders')
