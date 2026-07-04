from __future__ import annotations
"""Tag model for community group requests."""

import uuid

from sqlalchemy import Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class GroupRequestTag(Base):
    """Normalized tag attached to a pending or resolved group request."""

    __tablename__ = "group_request_tags"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    request_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("group_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: str = Column(String(50), nullable=False)

    __table_args__ = (
        Index("uq_group_request_tags_request_id_tag", "request_id", "tag", unique=True),
        Index("ix_group_request_tags_tag", "tag"),
    )

    def __repr__(self) -> str:
        return f"<GroupRequestTag(request_id={self.request_id}, tag={self.tag})>"
