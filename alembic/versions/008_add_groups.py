"""Add backward-compatible community groups tables and admin flag.

Revision ID: 008_add_groups
Revises: 007_add_food_intelligence
Create Date: 2026-07-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "008_add_groups"
down_revision = "007_add_food_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "groups",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("primary_category", sa.String(length=40), nullable=False),
        sa.Column("custom_category_label", sa.String(length=100), nullable=True),
        sa.Column("locality_label", sa.String(length=150), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_groups_status", "groups", ["status"])
    op.create_index("ix_groups_primary_category", "groups", ["primary_category"])
    op.create_index("ix_groups_city_state_country", "groups", ["city", "state", "country"])

    op.create_table(
        "group_tags",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_group_tags_group_id", "group_tags", ["group_id"])
    op.create_index("ix_group_tags_tag", "group_tags", ["tag"])
    op.create_index("uq_group_tags_group_id_tag", "group_tags", ["group_id", "tag"], unique=True)

    op.create_table(
        "group_memberships",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_reason", sa.Text(), nullable=True),
        sa.Column(
            "banned_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_index(
        "ix_group_memberships_group_id_status",
        "group_memberships",
        ["group_id", "status"],
    )
    op.create_index(
        "ix_group_memberships_user_id_status",
        "group_memberships",
        ["user_id", "status"],
    )
    op.create_index(
        "uq_group_memberships_group_id_user_id",
        "group_memberships",
        ["group_id", "user_id"],
        unique=True,
    )

    op.create_table(
        "group_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "removed_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("removal_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_group_messages_group_id", "group_messages", ["group_id"])
    op.create_index("ix_group_messages_sender_user_id", "group_messages", ["sender_user_id"])
    op.create_index(
        "ix_group_messages_group_id_created_at",
        "group_messages",
        ["group_id", "created_at"],
    )
    op.create_index(
        "ix_group_messages_group_id_status",
        "group_messages",
        ["group_id", "status"],
    )

    op.create_table(
        "group_message_attachments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("group_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attachment_kind", sa.String(length=20), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_group_message_attachments_message_id",
        "group_message_attachments",
        ["message_id"],
    )

    op.create_table(
        "group_requests",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_category", sa.String(length=40), nullable=False),
        sa.Column("custom_category_label", sa.String(length=100), nullable=True),
        sa.Column("locality_label", sa.String(length=150), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("request_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_group_requests_requester_user_id", "group_requests", ["requester_user_id"])
    op.create_index("ix_group_requests_status", "group_requests", ["status"])
    op.create_index("ix_group_requests_primary_category", "group_requests", ["primary_category"])
    op.create_index(
        "ix_group_requests_city_state_country",
        "group_requests",
        ["city", "state", "country"],
    )

    op.create_table(
        "group_request_tags",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            UUID(as_uuid=True),
            sa.ForeignKey("group_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_group_request_tags_request_id", "group_request_tags", ["request_id"])
    op.create_index("ix_group_request_tags_tag", "group_request_tags", ["tag"])
    op.create_index(
        "uq_group_request_tags_request_id_tag",
        "group_request_tags",
        ["request_id", "tag"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_group_request_tags_request_id_tag", table_name="group_request_tags")
    op.drop_index("ix_group_request_tags_tag", table_name="group_request_tags")
    op.drop_index("ix_group_request_tags_request_id", table_name="group_request_tags")
    op.drop_table("group_request_tags")

    op.drop_index("ix_group_requests_city_state_country", table_name="group_requests")
    op.drop_index("ix_group_requests_primary_category", table_name="group_requests")
    op.drop_index("ix_group_requests_status", table_name="group_requests")
    op.drop_index("ix_group_requests_requester_user_id", table_name="group_requests")
    op.drop_table("group_requests")

    op.drop_index("ix_group_message_attachments_message_id", table_name="group_message_attachments")
    op.drop_table("group_message_attachments")

    op.drop_index("ix_group_messages_group_id_status", table_name="group_messages")
    op.drop_index("ix_group_messages_group_id_created_at", table_name="group_messages")
    op.drop_index("ix_group_messages_sender_user_id", table_name="group_messages")
    op.drop_index("ix_group_messages_group_id", table_name="group_messages")
    op.drop_table("group_messages")

    op.drop_index("uq_group_memberships_group_id_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_user_id_status", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id_status", table_name="group_memberships")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_table("group_memberships")

    op.drop_index("uq_group_tags_group_id_tag", table_name="group_tags")
    op.drop_index("ix_group_tags_tag", table_name="group_tags")
    op.drop_index("ix_group_tags_group_id", table_name="group_tags")
    op.drop_table("group_tags")

    op.drop_index("ix_groups_city_state_country", table_name="groups")
    op.drop_index("ix_groups_primary_category", table_name="groups")
    op.drop_index("ix_groups_status", table_name="groups")
    op.drop_table("groups")

    op.drop_column("users", "is_admin")
