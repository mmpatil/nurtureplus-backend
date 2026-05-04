from __future__ import annotations
"""Baby access / membership model for caregiver collaboration."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class BabyAccess(Base):
    """
    Tracks who has access to a baby's data.

    Roles:
      - owner: the user who created the baby profile (one per baby)
      - caregiver: invited collaborator

    Statuses:
      - pending:  invite sent, not yet accepted
      - accepted: active access
      - revoked:  access removed
    """

    __tablename__ = "baby_access"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    baby_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("babies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,   # NULL until invite is accepted by a real user
        index=True,
    )
    role: str = Column(String(20), nullable=False)         # owner | caregiver
    status: str = Column(String(20), nullable=False)       # pending | accepted | revoked

    # Who sent the invite (NULL for the owner row created at baby creation)
    invited_by_user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Invite-specific fields (only populated for caregiver invites)
    invite_email: str = Column(String(255), nullable=True)
    invite_token: str = Column(String(128), nullable=True, unique=True)
    invite_expires_at: datetime = Column(DateTime(timezone=True), nullable=True)
    accepted_at: datetime = Column(DateTime(timezone=True), nullable=True)
    revoked_at: datetime = Column(DateTime(timezone=True), nullable=True)

    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_baby_access_baby_id", "baby_id"),
        Index("ix_baby_access_user_id", "user_id"),
        Index("ix_baby_access_invite_token", "invite_token"),
        Index(
            "uq_baby_access_owner_per_baby",
            "baby_id",
            unique=True,
            postgresql_where=text("role = 'owner' AND status = 'accepted'"),
        ),
        Index(
            "uq_baby_access_accepted_user_per_baby",
            "baby_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL AND status = 'accepted'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BabyAccess(id={self.id}, baby_id={self.baby_id}, "
            f"user_id={self.user_id}, role={self.role}, status={self.status})>"
        )
