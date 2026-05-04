"""Add caregiver collaboration: baby_access table, audit fields on entry tables,
user profile fields.

Revision ID: 006_add_caregiver_collaboration
Revises: 005_add_photo_url_to_milestones
Create Date: 2026-04-16 00:00:00.000000

Backfill notes
--------------
1. New columns on users (email, display_name, is_anonymous) default to
   NULL / False — safe to add with no backfill needed.
2. baby_access table is created fresh, then one owner row is inserted per
   existing baby using the baby's user_id.
3. created_by_user_id / updated_by_user_id are added as nullable columns,
   then backfilled from the baby's user_id (best-effort for historic data).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006_add_caregiver_collaboration"
down_revision = "005_add_photo_url_to_milestones"
branch_labels = None
depends_on = None

# Entry tables that need audit columns
BABY_ENTRY_TABLES = [
    "feeding_entries",
    "diaper_entries",
    "sleep_entries",
    "mood_entries",
    "growth_entries",
    "milestone_entries",
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add profile + anonymous flag to users
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ------------------------------------------------------------------
    # 2. Create baby_access table
    # ------------------------------------------------------------------
    op.create_table(
        "baby_access",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "baby_id",
            UUID(as_uuid=True),
            sa.ForeignKey("babies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "invited_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invite_email", sa.String(255), nullable=True),
        sa.Column("invite_token", sa.String(128), nullable=True, unique=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_baby_access_baby_id", "baby_access", ["baby_id"])
    op.create_index("ix_baby_access_user_id", "baby_access", ["user_id"])
    op.create_index("ix_baby_access_invite_token", "baby_access", ["invite_token"])
    op.create_index(
        "uq_baby_access_owner_per_baby",
        "baby_access",
        ["baby_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND status = 'accepted'"),
    )
    op.create_index(
        "uq_baby_access_accepted_user_per_baby",
        "baby_access",
        ["baby_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL AND status = 'accepted'"),
    )

    # ------------------------------------------------------------------
    # 3. Backfill: one owner row per existing baby
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO baby_access (id, baby_id, user_id, role, status, accepted_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            b.id,
            b.user_id,
            'owner',
            'accepted',
            b.created_at,
            b.created_at,
            b.created_at
        FROM babies b
        WHERE b.user_id IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # 4. Add audit columns to all entry tables
    # ------------------------------------------------------------------
    for table in BABY_ENTRY_TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_by_user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "updated_by_user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    op.add_column(
        "recovery_entries",
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "recovery_entries",
        sa.Column(
            "updated_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 5. Backfill audit columns from the baby's owning user
    #    (best-effort — new entries will be set correctly going forward)
    # ------------------------------------------------------------------
    for table in BABY_ENTRY_TABLES:
        op.execute(
            f"""
            UPDATE {table} e
            SET
                created_by_user_id = b.user_id,
                updated_by_user_id = b.user_id
            FROM babies b
            WHERE e.baby_id = b.id
              AND b.user_id IS NOT NULL
              AND e.created_by_user_id IS NULL
            """
        )

    op.execute(
        """
        UPDATE recovery_entries r
        SET
            created_by_user_id = r.user_id,
            updated_by_user_id = r.user_id
        WHERE r.user_id IS NOT NULL
          AND r.created_by_user_id IS NULL
        """
    )


def downgrade() -> None:
    # Remove audit columns from entry tables
    op.drop_column("recovery_entries", "updated_by_user_id")
    op.drop_column("recovery_entries", "created_by_user_id")

    for table in BABY_ENTRY_TABLES:
        op.drop_column(table, "updated_by_user_id")
        op.drop_column(table, "created_by_user_id")

    # Drop baby_access table
    op.drop_index("uq_baby_access_accepted_user_per_baby", table_name="baby_access")
    op.drop_index("uq_baby_access_owner_per_baby", table_name="baby_access")
    op.drop_index("ix_baby_access_invite_token", table_name="baby_access")
    op.drop_index("ix_baby_access_user_id", table_name="baby_access")
    op.drop_index("ix_baby_access_baby_id", table_name="baby_access")
    op.drop_table("baby_access")

    # Remove user profile fields
    op.drop_column("users", "is_anonymous")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
