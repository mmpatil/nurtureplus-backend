from __future__ import annotations
"""CRUD operations for milestone entries — membership-aware."""
import logging
from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.milestone_entry import MilestoneEntry
from app.models.baby_access import BabyAccess
from app.crud._baby_access_check import verify_baby_access
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate

logger = logging.getLogger(__name__)


def _as_utc_midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


async def get_milestone_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[MilestoneEntry], int]:
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    count_result = await db.execute(
        select(func.count(MilestoneEntry.id)).where(MilestoneEntry.baby_id == baby_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(MilestoneEntry)
        .where(MilestoneEntry.baby_id == baby_id)
        .order_by(MilestoneEntry.achieved_date.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_milestone_entry_by_id(
    db: AsyncSession,
    milestone_id: UUID,
    user_id: UUID,
) -> MilestoneEntry | None:
    result = await db.execute(
        select(MilestoneEntry)
        .join(BabyAccess, BabyAccess.baby_id == MilestoneEntry.baby_id)
        .where(
            MilestoneEntry.id == milestone_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_milestone_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    milestone_create: MilestoneCreate,
    autocommit: bool = True,
) -> MilestoneEntry | None:
    if not await verify_baby_access(db, baby_id, user_id):
        return None

    entry = MilestoneEntry(
        baby_id=baby_id,
        title=milestone_create.title,
        category=milestone_create.category,
        achieved_date=_as_utc_midnight(milestone_create.achieved_date),
        notes=milestone_create.notes,
        photo_url=str(milestone_create.photo_url) if milestone_create.photo_url else None,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(entry)
    if autocommit:
        await db.commit()
        await db.refresh(entry)
    else:
        await db.flush()
    return entry


async def update_milestone_entry(
    db: AsyncSession,
    milestone_id: UUID,
    user_id: UUID,
    milestone_update: MilestoneUpdate,
    is_owner: bool = False,
) -> MilestoneEntry | None:
    entry = await get_milestone_entry_by_id(db, milestone_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None

    for key, value in milestone_update.model_dump(exclude_unset=True).items():
        if key == "achieved_date" and value is not None:
            value = _as_utc_midnight(value)
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_milestone_entry(
    db: AsyncSession,
    milestone_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    entry = await get_milestone_entry_by_id(db, milestone_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(MilestoneEntry).where(MilestoneEntry.id == milestone_id))
    await db.commit()
    return True
