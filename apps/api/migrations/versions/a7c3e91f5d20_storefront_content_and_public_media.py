"""storefront content and public media

Revision ID: a7c3e91f5d20
Revises: 3e6d1cbd15fb
Create Date: 2026-10-23 09:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a7c3e91f5d20'
down_revision = '3e6d1cbd15fb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # categories: storefront presentation fields
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('slug', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('blurb', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('tone', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('image_file_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False))
        batch_op.create_index(batch_op.f('ix_categories_slug'), ['slug'], unique=False)
        batch_op.create_unique_constraint('uq_categories_company_slug', ['company_id', 'slug'])

    # products: storefront presentation fields
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('compare_at_price', sa.Numeric(18, 4), nullable=True))
        batch_op.add_column(sa.Column('badge', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('highlights', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('colors', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('rating_avg', sa.Numeric(3, 2), nullable=True))
        batch_op.add_column(sa.Column('rating_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('tone', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('slug', sa.String(length=80), nullable=True))
        batch_op.create_index(batch_op.f('ix_products_slug'), ['slug'], unique=False)
        batch_op.create_unique_constraint('uq_products_company_slug', ['company_id', 'slug'])

    op.create_table(
        'product_images',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=False),
        sa.Column('file_id', sa.String(length=36), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('alt', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_images_product_id_products')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_images')),
    )
    with op.batch_alter_table('product_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_images_company_id'), ['company_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_product_images_product_id'), ['product_id'], unique=False)

    op.create_table(
        'storefront_hero_slides',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('eyebrow', sa.String(length=80), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('cta', sa.String(length=80), nullable=False),
        sa.Column('category_slug', sa.String(length=80), nullable=True),
        sa.Column('tone', sa.String(length=16), nullable=False),
        sa.Column('image_file_id', sa.String(length=36), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storefront_hero_slides')),
    )
    with op.batch_alter_table('storefront_hero_slides', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storefront_hero_slides_company_id'), ['company_id'], unique=False)

    op.create_table(
        'storefront_testimonials',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('quote', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storefront_testimonials')),
    )
    with op.batch_alter_table('storefront_testimonials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storefront_testimonials_company_id'), ['company_id'], unique=False)

    op.create_table(
        'storefront_faqs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('group_name', sa.String(length=100), nullable=False),
        sa.Column('question', sa.String(length=300), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storefront_faqs')),
    )
    with op.batch_alter_table('storefront_faqs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storefront_faqs_company_id'), ['company_id'], unique=False)

    op.create_table(
        'storefront_policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('updated', sa.String(length=40), nullable=False),
        sa.Column('sections', sa.JSON(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storefront_policies')),
        sa.UniqueConstraint('company_id', 'slug', name='uq_storefront_policies_slug'),
    )
    with op.batch_alter_table('storefront_policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storefront_policies_company_id'), ['company_id'], unique=False)

    op.create_table(
        'storefront_settings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('free_shipping_threshold', sa.Numeric(18, 2), nullable=True),
        sa.Column('flat_shipping_fee', sa.Numeric(18, 2), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_address', sa.String(length=300), nullable=True),
        sa.Column('map_image_file_id', sa.String(length=36), nullable=True),
        sa.Column('announcements', sa.JSON(), nullable=True),
        sa.Column('perks', sa.JSON(), nullable=True),
        sa.Column('about_values', sa.JSON(), nullable=True),
        sa.Column('about_stats', sa.JSON(), nullable=True),
        sa.Column('footer_about', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('blamable', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_storefront_settings')),
        sa.UniqueConstraint('company_id', name='uq_storefront_settings_company'),
    )
    with op.batch_alter_table('storefront_settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_storefront_settings_company_id'), ['company_id'], unique=False)


def downgrade() -> None:
    op.drop_table('storefront_settings')
    op.drop_table('storefront_policies')
    op.drop_table('storefront_faqs')
    op.drop_table('storefront_testimonials')
    op.drop_table('storefront_hero_slides')
    op.drop_table('product_images')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('uq_products_company_slug', type_='unique')
        batch_op.drop_index(batch_op.f('ix_products_slug'))
        batch_op.drop_column('slug')
        batch_op.drop_column('tone')
        batch_op.drop_column('rating_count')
        batch_op.drop_column('rating_avg')
        batch_op.drop_column('colors')
        batch_op.drop_column('highlights')
        batch_op.drop_column('badge')
        batch_op.drop_column('compare_at_price')

    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint('uq_categories_company_slug', type_='unique')
        batch_op.drop_index(batch_op.f('ix_categories_slug'))
        batch_op.drop_column('is_active')
        batch_op.drop_column('sort_order')
        batch_op.drop_column('image_file_id')
        batch_op.drop_column('tone')
        batch_op.drop_column('blurb')
        batch_op.drop_column('slug')
