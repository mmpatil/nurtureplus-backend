"""Add photo_url to milestone_entries

Revision ID: 005_add_photo_url_to_milestones
Revises: 004_add_growth_and_milestone_entries
Create Date: 2026-04-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "005_add_photo_url_to_milestones"
down_revision = "004_add_growth_milestone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("milestone_entries", sa.Column("photo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("milestone_entries", "photo_url")
