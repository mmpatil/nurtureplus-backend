from __future__ import annotations
"""Tag model for community groups."""

import uuid

from sqlalchemy import Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class GroupTag(Base):
    """Normalized discovery tag attached to a group."""

    __tablename__ = "group_tags"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    group_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: str = Column(String(50), nullable=False)

    __table_args__ = (
        Index("uq_group_tags_group_id_tag", "group_id", "tag", unique=True),
        Index("ix_group_tags_tag", "tag"),
    )

    def __repr__(self) -> str:
        return f"<GroupTag(group_id={self.group_id}, tag={self.tag})>"
