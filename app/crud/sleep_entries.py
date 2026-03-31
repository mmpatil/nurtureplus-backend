"""CRUD operations for sleep entries."""
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sleep_entry import SleepEntry
from app.schemas.sleep import SleepCreate, SleepUpdate

logger = logging.getLogger(__name__)


def calculate_duration(start_time: datetime, end_time: datetime | None) -> int | None:
    """Calculate duration in minutes from start and end times."""
    if not end_time:
        return None
    delta = end_time - start_time
    return int(delta.total_seconds() / 60)


async def get_sleep_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[SleepEntry], int]:
    """
    Get sleep entries for a baby with optional date range filtering.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user (for ownership check)
        limit: Number of results (max 100)
        offset: Number of results to skip
        from_time: Start time filter (inclusive)
        to_time: End time filter (inclusive)
        
    Returns:
        Tuple of (sleep entries list, total count)
    """
    # First verify baby belongs to user
    from app.models.babies import Baby
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return [], 0
    
    # Build query with filters
    query = select(SleepEntry).where(SleepEntry.baby_id == baby_id)
    
    if from_time:
        query = query.where(SleepEntry.start_time >= from_time)
    if to_time:
        query = query.where(SleepEntry.start_time <= to_time)
    
    # Get total count
    count_query = select(func.count(SleepEntry.id)).where(SleepEntry.baby_id == baby_id)
    if from_time:
        count_query = count_query.where(SleepEntry.start_time >= from_time)
    if to_time:
        count_query = count_query.where(SleepEntry.start_time <= to_time)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    limit = min(limit, 100)
    offset = max(offset, 0)
    
    result = await db.execute(
        query.order_by(SleepEntry.start_time.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    
    return entries, total


async def get_sleep_entry_by_id(
    db: AsyncSession,
    sleep_id: UUID,
    user_id: UUID,
) -> SleepEntry | None:
    """
    Get a sleep entry by ID, with ownership check.
    
    Args:
        db: Database session
        sleep_id: UUID of the sleep entry
        user_id: UUID of the authenticated user
        
    Returns:
        SleepEntry object or None if not found or not owned by user
    """
    from app.models.babies import Baby
    
    result = await db.execute(
        select(SleepEntry).join(Baby).where(
            (SleepEntry.id == sleep_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_sleep_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    sleep_create: SleepCreate,
) -> SleepEntry | None:
    """
    Create a sleep entry for a baby.
    
    Auto-calculates duration_min if end_time is provided.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        sleep_create: Sleep creation schema
        
    Returns:
        Created SleepEntry or None if baby doesn't belong to user
    """
    from app.models.babies import Baby
    
    # Verify baby belongs to user
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return None
    
    # Auto-calculate duration if end_time provided and duration_min not set
    duration_min = sleep_create.duration_min
    if not duration_min and sleep_create.end_time:
        duration_min = calculate_duration(sleep_create.start_time, sleep_create.end_time)
    
    sleep = SleepEntry(
        baby_id=baby_id,
        start_time=sleep_create.start_time,
        end_time=sleep_create.end_time,
        duration_min=duration_min,
        quality=sleep_create.quality,
        notes=sleep_create.notes,
    )
    db.add(sleep)
    await db.commit()
    await db.refresh(sleep)
    
    return sleep


async def update_sleep_entry(
    db: AsyncSession,
    sleep_id: UUID,
    user_id: UUID,
    sleep_update: SleepUpdate,
) -> SleepEntry | None:
    """
    Update a sleep entry.
    
    Auto-calculates duration_min if end_time is updated.
    
    Args:
        db: Database session
        sleep_id: UUID of the sleep entry
        user_id: UUID of the authenticated user
        sleep_update: Sleep update schema
        
    Returns:
        Updated SleepEntry or None if not found or not owned by user
    """
    entry = await get_sleep_entry_by_id(db, sleep_id, user_id)
    if not entry:
        return None
    
    update_data = sleep_update.model_dump(exclude_unset=True)
    
    # Auto-calculate duration if end_time is being updated
    if 'end_time' in update_data and not ('duration_min' in update_data):
        start = entry.start_time
        end = update_data.get('end_time')
        if end:
            update_data['duration_min'] = calculate_duration(start, end)
    
    for key, value in update_data.items():
        setattr(entry, key, value)
    
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    
    return entry


async def delete_sleep_entry(
    db: AsyncSession,
    sleep_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a sleep entry.
    
    Args:
        db: Database session
        sleep_id: UUID of the sleep entry
        user_id: UUID of the authenticated user
        
    Returns:
        True if deleted, False if not found or not owned by user
    """
    result = await db.execute(
        delete(SleepEntry).where(
            SleepEntry.id == sleep_id
        ).returning(SleepEntry.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
