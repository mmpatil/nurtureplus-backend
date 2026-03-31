"""Baby database model."""
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Baby(Base):
    """Baby model for storing infant data."""
    
    __tablename__ = "babies"
    
    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: str = Column(String(100), nullable=False)
    birth_date: date = Column(Date, nullable=False)
    photo_url: str = Column(String(500), nullable=True)
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
    
    # Indexes for query optimization: scoped by user_id
    __table_args__ = (
        Index("ix_babies_user_id", "user_id"),
        Index("ix_babies_user_id_birth_date", "user_id", "birth_date"),
    )
    
    def __repr__(self) -> str:
        return f"<Baby(id={self.id}, user_id={self.user_id}, name={self.name})>"
