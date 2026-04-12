"""Add growth_entries and milestone_entries tables

Revision ID: 004_add_growth_and_milestone_entries
Revises: 003_add_recovery_entries
Create Date: 2026-04-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004_add_growth_milestone"
down_revision = "003_add_recovery_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "growth_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("baby_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("measurement_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("head_circumference_cm", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["baby_id"],
            ["babies.id"],
            name="fk_growth_entries_baby_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_growth_entries_baby_id", "growth_entries", ["baby_id"])
    op.create_index("ix_growth_entries_baby_id_date", "growth_entries", ["baby_id", "measurement_date"])

    op.create_table(
        "milestone_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("baby_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("achieved_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["baby_id"],
            ["babies.id"],
            name="fk_milestone_entries_baby_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_milestone_entries_baby_id", "milestone_entries", ["baby_id"])
    op.create_index("ix_milestone_entries_baby_id_date", "milestone_entries", ["baby_id", "achieved_date"])


def downgrade() -> None:
    op.drop_index("ix_milestone_entries_baby_id_date", table_name="milestone_entries")
    op.drop_index("ix_milestone_entries_baby_id", table_name="milestone_entries")
    op.drop_table("milestone_entries")

    op.drop_index("ix_growth_entries_baby_id_date", table_name="growth_entries")
    op.drop_index("ix_growth_entries_baby_id", table_name="growth_entries")
    op.drop_table("growth_entries")
