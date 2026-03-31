"""CRUD operations for feeding entries."""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.feeding_entry import FeedingEntry
from app.schemas.feeding import FeedingCreate, FeedingUpdate

logger = logging.getLogger(__name__)


async def get_feeding_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[FeedingEntry], int]:
    """
    Get feeding entries for a baby with optional date range filtering.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user (for ownership check)
        limit: Number of results (max 100)
        offset: Number of results to skip
        from_time: Start time filter (inclusive)
        to_time: End time filter (inclusive)
        
    Returns:
        Tuple of (feeding entries list, total count)
    """
    # First verify baby belongs to user
    from app.models.babies import Baby
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return [], 0
    
    # Build query with filters
    query = select(FeedingEntry).where(FeedingEntry.baby_id == baby_id)
    
    if from_time:
        query = query.where(FeedingEntry.timestamp >= from_time)
    if to_time:
        query = query.where(FeedingEntry.timestamp <= to_time)
    
    # Get total count
    count_query = select(func.count(FeedingEntry.id)).where(FeedingEntry.baby_id == baby_id)
    if from_time:
        count_query = count_query.where(FeedingEntry.timestamp >= from_time)
    if to_time:
        count_query = count_query.where(FeedingEntry.timestamp <= to_time)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    limit = min(limit, 100)
    offset = max(offset, 0)
    
    result = await db.execute(
        query.order_by(FeedingEntry.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    
    return entries, total


async def get_feeding_entry_by_id(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
) -> FeedingEntry | None:
    """
    Get a feeding entry by ID, with ownership check.
    
    Args:
        db: Database session
        feeding_id: UUID of the feeding entry
        user_id: UUID of the authenticated user
        
    Returns:
        FeedingEntry object or None if not found or not owned by user
    """
    from app.models.babies import Baby
    
    result = await db.execute(
        select(FeedingEntry).join(Baby).where(
            (FeedingEntry.id == feeding_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_feeding_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    feeding_create: FeedingCreate,
) -> FeedingEntry | None:
    """
    Create a feeding entry for a baby.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        feeding_create: Feeding creation schema
        
    Returns:
        Created FeedingEntry or None if baby doesn't belong to user
    """
    from app.models.babies import Baby
    
    # Verify baby belongs to user
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return None
    
    feeding = FeedingEntry(
        baby_id=baby_id,
        feeding_type=feeding_create.feeding_type,
        amount_ml=feeding_create.amount_ml,
        duration_min=feeding_create.duration_min,
        timestamp=feeding_create.timestamp,
        notes=feeding_create.notes,
    )
    db.add(feeding)
    await db.commit()
    await db.refresh(feeding)
    
    return feeding


async def update_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
    feeding_update: FeedingUpdate,
) -> FeedingEntry | None:
    """
    Update a feeding entry.
    
    Args:
        db: Database session
        feeding_id: UUID of the feeding entry
        user_id: UUID of the authenticated user
        feeding_update: Feeding update schema
        
    Returns:
        Updated FeedingEntry or None if not found or not owned by user
    """
    entry = await get_feeding_entry_by_id(db, feeding_id, user_id)
    if not entry:
        return None
    
    update_data = feeding_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    
    return entry


async def delete_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a feeding entry.
    
    Args:
        db: Database session
        feeding_id: UUID of the feeding entry
        user_id: UUID of the authenticated user
        
    Returns:
        True if deleted, False if not found or not owned by user
    """
    result = await db.execute(
        delete(FeedingEntry).where(
            FeedingEntry.id == feeding_id
        ).returning(FeedingEntry.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
