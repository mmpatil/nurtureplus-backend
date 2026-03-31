"""CRUD operations for mood entries."""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.mood_entry import MoodEntry
from app.schemas.mood import MoodCreate, MoodUpdate

logger = logging.getLogger(__name__)


async def get_mood_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[MoodEntry], int]:
    """
    Get mood entries for a baby with optional date range filtering.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user (for ownership check)
        limit: Number of results (max 100)
        offset: Number of results to skip
        from_time: Start time filter (inclusive)
        to_time: End time filter (inclusive)
        
    Returns:
        Tuple of (mood entries list, total count)
    """
    # First verify baby belongs to user
    from app.models.babies import Baby
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return [], 0
    
    # Build query with filters
    query = select(MoodEntry).where(MoodEntry.baby_id == baby_id)
    
    if from_time:
        query = query.where(MoodEntry.timestamp >= from_time)
    if to_time:
        query = query.where(MoodEntry.timestamp <= to_time)
    
    # Get total count
    count_query = select(func.count(MoodEntry.id)).where(MoodEntry.baby_id == baby_id)
    if from_time:
        count_query = count_query.where(MoodEntry.timestamp >= from_time)
    if to_time:
        count_query = count_query.where(MoodEntry.timestamp <= to_time)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    limit = min(limit, 100)
    offset = max(offset, 0)
    
    result = await db.execute(
        query.order_by(MoodEntry.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    
    return entries, total


async def get_mood_entry_by_id(
    db: AsyncSession,
    mood_id: UUID,
    user_id: UUID,
) -> MoodEntry | None:
    """
    Get a mood entry by ID, with ownership check.
    
    Args:
        db: Database session
        mood_id: UUID of the mood entry
        user_id: UUID of the authenticated user
        
    Returns:
        MoodEntry object or None if not found or not owned by user
    """
    from app.models.babies import Baby
    
    result = await db.execute(
        select(MoodEntry).join(Baby).where(
            (MoodEntry.id == mood_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_mood_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    mood_create: MoodCreate,
) -> MoodEntry | None:
    """
    Create a mood entry for a baby.
    
    Args:
        db: Database session
        baby_id: UUID of the baby
        user_id: UUID of the authenticated user
        mood_create: Mood creation schema
        
    Returns:
        Created MoodEntry or None if baby doesn't belong to user
    """
    from app.models.babies import Baby
    
    # Verify baby belongs to user
    baby_result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    if not baby_result.scalar_one_or_none():
        return None
    
    mood = MoodEntry(
        baby_id=baby_id,
        mood=mood_create.mood,
        energy=mood_create.energy,
        timestamp=mood_create.timestamp,
        notes=mood_create.notes,
    )
    db.add(mood)
    await db.commit()
    await db.refresh(mood)
    
    return mood


async def update_mood_entry(
    db: AsyncSession,
    mood_id: UUID,
    user_id: UUID,
    mood_update: MoodUpdate,
) -> MoodEntry | None:
    """
    Update a mood entry.
    
    Args:
        db: Database session
        mood_id: UUID of the mood entry
        user_id: UUID of the authenticated user
        mood_update: Mood update schema
        
    Returns:
        Updated MoodEntry or None if not found or not owned by user
    """
    entry = await get_mood_entry_by_id(db, mood_id, user_id)
    if not entry:
        return None
    
    update_data = mood_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    
    return entry


async def delete_mood_entry(
    db: AsyncSession,
    mood_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Delete a mood entry.
    
    Args:
        db: Database session
        mood_id: UUID of the mood entry
        user_id: UUID of the authenticated user
        
    Returns:
        True if deleted, False if not found or not owned by user
    """
    result = await db.execute(
        delete(MoodEntry).where(
            MoodEntry.id == mood_id
        ).returning(MoodEntry.id)
    )
    await db.commit()
    return result.scalar_one_or_none() is not None
