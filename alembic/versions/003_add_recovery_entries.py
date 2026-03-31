"""Add recovery_entries table for postpartum recovery tracking

Revision ID: 003_add_recovery_entries
Revises: 002_add_tracking_entries
Create Date: 2026-03-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_add_recovery_entries"
down_revision = "002_add_tracking_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create recovery_entries table for user postpartum recovery tracking."""
    op.create_table(
        "recovery_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mood", sa.String(20), nullable=False),
        sa.Column("energy_level", sa.String(20), nullable=False),
        sa.Column("water_intake_oz", sa.Integer(), nullable=False),
        sa.Column("symptoms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
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
            ["user_id"],
            ["users.id"],
            name="fk_recovery_entries_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for query optimization
    op.create_index("ix_recovery_entries_user_id", "recovery_entries", ["user_id"])
    op.create_index("ix_recovery_entries_user_timestamp", "recovery_entries", ["user_id", "timestamp"])
    op.create_index("ix_recovery_entries_timestamp", "recovery_entries", ["timestamp"])


def downgrade() -> None:
    """Drop recovery_entries table."""
    op.drop_index("ix_recovery_entries_timestamp", table_name="recovery_entries")
    op.drop_index("ix_recovery_entries_user_timestamp", table_name="recovery_entries")
    op.drop_index("ix_recovery_entries_user_id", table_name="recovery_entries")
    op.drop_table("recovery_entries")
