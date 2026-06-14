from __future__ import annotations
"""CRUD operations for diaper entries — membership-aware."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diaper_entry import DiaperEntry
from app.models.baby_access import BabyAccess
from app.crud._baby_access_check import verify_baby_access
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
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    base_filter = [DiaperEntry.baby_id == baby_id]
    if from_time:
        base_filter.append(DiaperEntry.timestamp >= from_time)
    if to_time:
        base_filter.append(DiaperEntry.timestamp <= to_time)

    count_result = await db.execute(
        select(func.count(DiaperEntry.id)).where(*base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(DiaperEntry)
        .where(*base_filter)
        .order_by(DiaperEntry.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_diaper_entry_by_id(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
) -> DiaperEntry | None:
    result = await db.execute(
        select(DiaperEntry)
        .join(BabyAccess, BabyAccess.baby_id == DiaperEntry.baby_id)
        .where(
            DiaperEntry.id == diaper_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_diaper_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    diaper_create: DiaperCreate,
    autocommit: bool = True,
) -> DiaperEntry | None:
    if not await verify_baby_access(db, baby_id, user_id):
        return None

    diaper = DiaperEntry(
        baby_id=baby_id,
        diaper_type=diaper_create.diaper_type,
        timestamp=diaper_create.timestamp,
        notes=diaper_create.notes,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(diaper)
    if autocommit:
        await db.commit()
        await db.refresh(diaper)
    else:
        await db.flush()
    return diaper


async def update_diaper_entry(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
    diaper_update: DiaperUpdate,
    is_owner: bool = False,
) -> DiaperEntry | None:
    entry = await get_diaper_entry_by_id(db, diaper_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None

    for key, value in diaper_update.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_diaper_entry(
    db: AsyncSession,
    diaper_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    entry = await get_diaper_entry_by_id(db, diaper_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(DiaperEntry).where(DiaperEntry.id == diaper_id))
    await db.commit()
    return True
