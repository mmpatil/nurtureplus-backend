from __future__ import annotations
"""Attachment model for community group messages."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class GroupMessageAttachment(Base):
    """URL-backed attachment metadata for a group message."""

    __tablename__ = "group_message_attachments"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    message_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("group_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attachment_kind: str = Column(String(20), nullable=False)
    url: str = Column(Text, nullable=False)
    mime_type: str = Column(String(200), nullable=True)
    file_name: str = Column(String(255), nullable=True)
    size_bytes: int = Column(BigInteger, nullable=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_group_message_attachments_message_id", "message_id"),
    )

    def __repr__(self) -> str:
        return f"<GroupMessageAttachment(message_id={self.message_id}, kind={self.attachment_kind})>"
