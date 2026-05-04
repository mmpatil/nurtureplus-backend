from __future__ import annotations
"""CRUD operations for mood entries — membership-aware."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mood_entry import MoodEntry
from app.models.baby_access import BabyAccess
from app.crud._baby_access_check import verify_baby_access
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
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    base_filter = [MoodEntry.baby_id == baby_id]
    if from_time:
        base_filter.append(MoodEntry.timestamp >= from_time)
    if to_time:
        base_filter.append(MoodEntry.timestamp <= to_time)

    count_result = await db.execute(
        select(func.count(MoodEntry.id)).where(*base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(MoodEntry)
        .where(*base_filter)
        .order_by(MoodEntry.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_mood_entry_by_id(
    db: AsyncSession,
    mood_id: UUID,
    user_id: UUID,
) -> MoodEntry | None:
    result = await db.execute(
        select(MoodEntry)
        .join(BabyAccess, BabyAccess.baby_id == MoodEntry.baby_id)
        .where(
            MoodEntry.id == mood_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_mood_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    mood_create: MoodCreate,
) -> MoodEntry | None:
    if not await verify_baby_access(db, baby_id, user_id):
        return None

    mood = MoodEntry(
        baby_id=baby_id,
        mood=mood_create.mood,
        energy=mood_create.energy,
        timestamp=mood_create.timestamp,
        notes=mood_create.notes,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
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
    is_owner: bool = False,
) -> MoodEntry | None:
    entry = await get_mood_entry_by_id(db, mood_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None

    for key, value in mood_update.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_mood_entry(
    db: AsyncSession,
    mood_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    entry = await get_mood_entry_by_id(db, mood_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(MoodEntry).where(MoodEntry.id == mood_id))
    await db.commit()
    return True
