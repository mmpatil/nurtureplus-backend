"""CRUD operations for recovery entries."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recovery_entry import RecoveryEntry
from app.schemas.recovery import RecoveryEntryCreate, RecoveryEntryUpdate

logger = logging.getLogger(__name__)


async def create_recovery_entry(
    db: AsyncSession,
    user_id: UUID,
    entry: RecoveryEntryCreate,
) -> RecoveryEntry:
    """Create a new recovery entry for the user."""
    db_entry = RecoveryEntry(
        user_id=user_id,
        timestamp=entry.timestamp,
        mood=entry.mood,
        energy_level=entry.energy_level,
        water_intake_oz=entry.water_intake_oz,
        symptoms=entry.symptoms or [],
        notes=entry.notes,
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    logger.info(f"Created recovery entry: id={db_entry.id}, user_id={user_id}, mood={entry.mood}")
    return db_entry


async def list_recovery_entries(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
) -> tuple[List[RecoveryEntry], int]:
    """List recovery entries for user (newest first), with optional time filtering."""
    # Build query with user_id filter
    query = select(RecoveryEntry).where(RecoveryEntry.user_id == user_id)

    # Apply time filters if provided
    if from_time:
        query = query.where(RecoveryEntry.timestamp >= from_time)
    if to_time:
        query = query.where(RecoveryEntry.timestamp <= to_time)

    # Order by timestamp descending (newest first)
    query = query.order_by(RecoveryEntry.timestamp.desc())

    # Get total count
    count_result = await db.execute(select(RecoveryEntry).where(RecoveryEntry.user_id == user_id))
    total = len(count_result.scalars().all())

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    entries = result.scalars().all()

    logger.info(f"Listed {len(entries)} recovery entries for user_id={user_id}")
    return entries, total


async def get_recovery_entry(
    db: AsyncSession,
    entry_id: UUID,
    user_id: UUID,
) -> Optional[RecoveryEntry]:
    """Get a recovery entry by ID, checking ownership."""
    query = select(RecoveryEntry).where(
        and_(
            RecoveryEntry.id == entry_id,
            RecoveryEntry.user_id == user_id,
        )
    )
    result = await db.execute(query)
    entry = result.scalars().first()

    if entry:
        logger.info(f"Retrieved recovery entry: id={entry_id}, user_id={user_id}")
    else:
        logger.warning(f"Recovery entry not found or unauthorized: id={entry_id}, user_id={user_id}")
    return entry


async def get_latest_recovery_entry(
    db: AsyncSession,
    user_id: UUID,
) -> Optional[RecoveryEntry]:
    """Get the most recent recovery entry for the user."""
    query = (
        select(RecoveryEntry)
        .where(RecoveryEntry.user_id == user_id)
        .order_by(RecoveryEntry.timestamp.desc())
        .limit(1)
    )
    result = await db.execute(query)
    entry = result.scalars().first()

    if entry:
        logger.info(f"Retrieved latest recovery entry for user_id={user_id}")
    return entry


async def update_recovery_entry(
    db: AsyncSession,
    entry_id: UUID,
    user_id: UUID,
    entry_update: RecoveryEntryUpdate,
) -> Optional[RecoveryEntry]:
    """Update a recovery entry (partial update allowed)."""
    # Get entry and check ownership
    db_entry = await get_recovery_entry(db, entry_id, user_id)
    if not db_entry:
        return None

    # Update only provided fields
    update_data = entry_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_entry, field, value)

    db_entry.updated_at = datetime.now(timezone.utc)

    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)

    logger.info(f"Updated recovery entry: id={entry_id}, user_id={user_id}")
    return db_entry


async def delete_recovery_entry(
    db: AsyncSession,
    entry_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a recovery entry, checking ownership."""
    db_entry = await get_recovery_entry(db, entry_id, user_id)
    if not db_entry:
        return False

    await db.delete(db_entry)
    await db.commit()

    logger.info(f"Deleted recovery entry: id={entry_id}, user_id={user_id}")
    return True


async def get_recovery_summary(
    db: AsyncSession,
    user_id: UUID,
    days: int = 7,
) -> dict:
    """Get recovery summary for the user over the specified number of days."""
    # Calculate start time
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)

    # Query entries in the time window
    query = select(RecoveryEntry).where(
        and_(
            RecoveryEntry.user_id == user_id,
            RecoveryEntry.timestamp >= start_time,
        )
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    # Calculate metrics
    check_in_count = len(entries)
    average_water_intake = 0.0
    if entries:
        total_water = sum(e.water_intake_oz for e in entries)
        average_water_intake = total_water / check_in_count

    # Get latest entry
    latest = await get_latest_recovery_entry(db, user_id)

    logger.info(
        f"Generated recovery summary for user_id={user_id}, days={days}, check_ins={check_in_count}"
    )

    return {
        "days": days,
        "average_water_intake_oz": round(average_water_intake, 1),
        "check_in_count": check_in_count,
        "latest_entry": latest,
    }
