"""CRUD operations for babies."""
import logging
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.babies import Baby
from app.models.users import User
from app.schemas.baby import BabyCreate, BabyUpdate

logger = logging.getLogger(__name__)


async def get_babies_for_user(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Baby], int]:
    """
    Get all babies for a user with pagination.
    
    Optimized query with proper indexing on user_id.
    
    Args:
        db: Database session
        user_id: UUID of the user
        limit: Number of results (max 100)
        offset: Number of results to skip
        
    Returns:
        Tuple of (babies list, total count)
    """
    # Ensure limit is reasonable
    limit = min(limit, 100)
    offset = max(offset, 0)
    
    # Get total count with efficient query
    count_result = await db.execute(
        select(func.count(Baby.id)).where(Baby.user_id == user_id)
    )
    total = count_result.scalar() or 0
    
    # Get paginated results, ordered by created_at for consistency
    result = await db.execute(
        select(Baby)
        .where(Baby.user_id == user_id)
        .order_by(Baby.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    babies = result.scalars().all()
    
    return babies, total


async def get_baby_by_id(db: AsyncSession, baby_id: UUID, user_id: UUID) -> Baby | None:
    """
    Get a baby by ID, scoped to the user (security check).
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        
    Returns:
        Baby object or None if not found or not owned by user
    """
    result = await db.execute(
        select(Baby).where(
            (Baby.id == baby_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_baby(
    db: AsyncSession,
    user_id: UUID,
    baby_create: BabyCreate,
) -> Baby:
    """
    Create a new baby for the authenticated user.
    
    Args:
        db: Database session
        user_id: UUID of the authenticated user
        baby_create: Baby creation schema
        
    Returns:
        Created Baby object
    """
    baby = Baby(
        user_id=user_id,
        name=baby_create.name,
        birth_date=baby_create.birth_date,
        photo_url=baby_create.photo_url,
    )
    db.add(baby)
    await db.commit()
    await db.refresh(baby)
    logger.info(f"Created baby: {baby.id} for user: {user_id}")
    return baby


async def update_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    baby_update: BabyUpdate,
) -> Baby | None:
    """
    Update a baby, scoped to the user.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        baby_update: Baby update schema
        
    Returns:
        Updated Baby object or None if not found
    """
    # Fetch the baby (with user scoping for security)
    baby = await get_baby_by_id(db, baby_id, user_id)
    if not baby:
        return None
    
    # Update only provided fields
    if baby_update.name is not None:
        baby.name = baby_update.name
    if baby_update.birth_date is not None:
        baby.birth_date = baby_update.birth_date
    if baby_update.photo_url is not None:
        baby.photo_url = baby_update.photo_url
    
    await db.commit()
    await db.refresh(baby)
    logger.info(f"Updated baby: {baby.id}")
    return baby


async def delete_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a baby, scoped to the user.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        
    Returns:
        True if deleted, False if not found
    """
    # First verify the baby belongs to the user
    baby = await get_baby_by_id(db, baby_id, user_id)
    if not baby:
        return False
    
    # Delete the baby
    await db.execute(
        delete(Baby).where(
            (Baby.id == baby_id) & (Baby.user_id == user_id)
        )
    )
    await db.commit()
    logger.info(f"Deleted baby: {baby_id} for user: {user_id}")
    return True
