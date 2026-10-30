"""add payment gateways (superseded — intentionally a no-op)

Revision ID: a337a5b704e8
Revises: 97cb3b5c6b6b
Create Date: 2026-10-27 19:14:57.278592

This revision created the plaintext-credential `payment_gateways` table on the
pre-monorepo `main` branch. The merged code keeps the Fernet-encrypted
`payment_gateway_configs` table (b3f7d21a9c04) instead, so the revision id is
kept only to preserve the chain for databases that already applied it; the
merge revision c9e4a2f61b37 drops the leftover table if it exists.
"""

revision = 'a337a5b704e8'
down_revision = '97cb3b5c6b6b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
