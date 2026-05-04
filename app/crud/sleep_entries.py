from __future__ import annotations
"""CRUD operations for sleep entries — membership-aware."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sleep_entry import SleepEntry
from app.models.baby_access import BabyAccess
from app.crud._baby_access_check import verify_baby_access
from app.schemas.sleep import SleepCreate, SleepUpdate

logger = logging.getLogger(__name__)


def calculate_duration(start_time: datetime, end_time: datetime | None) -> int | None:
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
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    base_filter = [SleepEntry.baby_id == baby_id]
    if from_time:
        base_filter.append(SleepEntry.start_time >= from_time)
    if to_time:
        base_filter.append(SleepEntry.start_time <= to_time)

    count_result = await db.execute(
        select(func.count(SleepEntry.id)).where(*base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(SleepEntry)
        .where(*base_filter)
        .order_by(SleepEntry.start_time.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_sleep_entry_by_id(
    db: AsyncSession,
    sleep_id: UUID,
    user_id: UUID,
) -> SleepEntry | None:
    result = await db.execute(
        select(SleepEntry)
        .join(BabyAccess, BabyAccess.baby_id == SleepEntry.baby_id)
        .where(
            SleepEntry.id == sleep_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_sleep_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    sleep_create: SleepCreate,
) -> SleepEntry | None:
    if not await verify_baby_access(db, baby_id, user_id):
        return None

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
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
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
    is_owner: bool = False,
) -> SleepEntry | None:
    entry = await get_sleep_entry_by_id(db, sleep_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None

    update_data = sleep_update.model_dump(exclude_unset=True)
    if "end_time" in update_data and "duration_min" not in update_data:
        end = update_data.get("end_time")
        if end:
            update_data["duration_min"] = calculate_duration(entry.start_time, end)

    for key, value in update_data.items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_sleep_entry(
    db: AsyncSession,
    sleep_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    entry = await get_sleep_entry_by_id(db, sleep_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(SleepEntry).where(SleepEntry.id == sleep_id))
    await db.commit()
    return True
