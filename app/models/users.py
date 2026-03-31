"""User database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class User(Base):
    """User model for storing authenticated users from Firebase."""
    
    __tablename__ = "users"
    
    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    firebase_uid: str = Column(String(255), unique=True, nullable=False, index=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    # Indexes for query optimization
    __table_args__ = (
        Index("ix_users_firebase_uid", "firebase_uid", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, firebase_uid={self.firebase_uid})>"
