"""CRUD operations for milestone entries."""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.milestone_entry import MilestoneEntry
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate

logger = logging.getLogger(__name__)


async def _verify_baby_ownership(db: AsyncSession, baby_id: UUID, user_id: UUID) -> bool:
    from app.models.babies import Baby
    result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    return result.scalar_one_or_none() is not None


async def get_milestone_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[MilestoneEntry], int]:
    if not await _verify_baby_ownership(db, baby_id, user_id):
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
    from app.models.babies import Baby
    result = await db.execute(
        select(MilestoneEntry).join(Baby).where(
            (MilestoneEntry.id == milestone_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_milestone_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    milestone_create: MilestoneCreate,
) -> MilestoneEntry | None:
    if not await _verify_baby_ownership(db, baby_id, user_id):
        return None

    entry = MilestoneEntry(
        baby_id=baby_id,
        title=milestone_create.title,
        category=milestone_create.category,
        achieved_date=milestone_create.achieved_date,
        notes=milestone_create.notes,
        photo_url=str(milestone_create.photo_url) if milestone_create.photo_url else None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_milestone_entry(
    db: AsyncSession,
    milestone_id: UUID,
    user_id: UUID,
    milestone_update: MilestoneUpdate,
) -> MilestoneEntry | None:
    entry = await get_milestone_entry_by_id(db, milestone_id, user_id)
    if not entry:
        return None

    for key, value in milestone_update.model_dump(exclude_unset=True, mode="json").items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_milestone_entry(
    db: AsyncSession,
    milestone_id: UUID,
    user_id: UUID,
) -> bool:
    entry = await get_milestone_entry_by_id(db, milestone_id, user_id)
    if not entry:
        return False
    await db.execute(delete(MilestoneEntry).where(MilestoneEntry.id == milestone_id))
    await db.commit()
    return True
