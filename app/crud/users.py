"""CRUD operations for users."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.users import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


async def get_user_by_firebase_uid(db: AsyncSession, firebase_uid: str) -> User | None:
    """Get user by Firebase UID."""
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Get user by UUID."""
    from uuid import UUID
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """Create a new user."""
    user = User(firebase_uid=user_create.firebase_uid)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info(f"Created user: {user.id}")
    return user
