"""CRUD operations for diaper entries."""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.diaper_entry import DiaperEntry
from app.schemas.diaper import DiaperCreate, DiaperUpdate

logger = logging.getLogger(__name__)


async def get_diaper_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[DiaperEntry], int]:
    """
    Get diaper entries for a baby with optional date range filtering.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user (for ownership check)
        limit: Number of results (max 100)
        offset: Number of results to skip
        from_time: Start time filter (inclusive)
        to_time: End time filter (inclusive)
        
    Returns:
        Tuple of (diaper entries list, total count)
    """
    # First verify baby belongs to user
    from app.models.babies import Baby
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return [], 0
    
    # Build query with filters
    query = select(DiaperEntry).where(DiaperEntry.baby_id == baby_id)
    
    if from_time:
        query = query.where(DiaperEntry.timestamp >= from_time)
    if to_time:
        query = query.where(DiaperEntry.timestamp <= to_time)
    
    # Get total count
    count_query = select(func.count(DiaperEntry.id)).where(DiaperEntry.baby_id == baby_id)
    if from_time:
        count_query = count_query.where(DiaperEntry.timestamp >= from_time)
    if to_time:
        count_query = count_query.where(DiaperEntry.timestamp <= to_time)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    limit = min(limit, 100)
    offset = max(offset, 0)
    
    result = await db.execute(
        query.order_by(DiaperEntry.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    
    return entries, total


async def get_diaper_entry_by_id(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
) -> DiaperEntry | None:
    """
    Get a diaper entry by ID, with ownership check.
    
    Args:
        db: Database session
        diaper_id: UUID of the diaper entry
        user_id: UUID of the authenticated user
        
    Returns:
        DiaperEntry object or None if not found or not owned by user
    """
    from app.models.babies import Baby
    
    result = await db.execute(
        select(DiaperEntry).join(Baby).where(
            (DiaperEntry.id == diaper_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_diaper_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    diaper_create: DiaperCreate,
) -> DiaperEntry | None:
    """
    Create a diaper entry for a baby.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        diaper_create: Diaper creation schema
        
    Returns:
        Created DiaperEntry or None if baby doesn't belong to user
    """
    from app.models.babies import Baby
    
    # Verify baby belongs to user
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return None
    
    diaper = DiaperEntry(
        baby_id=baby_id,
        diaper_type=diaper_create.diaper_type,
        timestamp=diaper_create.timestamp,
        notes=diaper_create.notes,
    )
    db.add(diaper)
    await db.commit()
    await db.refresh(diaper)
    
    return diaper


async def update_diaper_entry(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
    diaper_update: DiaperUpdate,
) -> DiaperEntry | None:
    """
    Update a diaper entry.
    
    Args:
        db: Database session
        diaper_id: UUID of the diaper entry
        user_id: UUID of the authenticated user
        diaper_update: Diaper update schema
        
    Returns:
        Updated DiaperEntry or None if not found or not owned by user
    """
    entry = await get_diaper_entry_by_id(db, diaper_id, user_id)
    if not entry:
        return None
    
    update_data = diaper_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    
    return entry


async def delete_diaper_entry(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a diaper entry.
    
    Args:
        db: Database session
        diaper_id: UUID of the diaper entry
        user_id: UUID of the authenticated user
        
    Returns:
        True if deleted, False if not found or not owned by user
    """
    result = await db.execute(
        delete(DiaperEntry).where(
            DiaperEntry.id == diaper_id
        ).returning(DiaperEntry.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
