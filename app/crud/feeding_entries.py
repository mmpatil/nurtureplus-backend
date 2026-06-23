from __future__ import annotations
"""CRUD operations for feeding entries — membership-aware."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feeding_entry import FeedingEntry
from app.models.babies import Baby
from app.models.baby_access import BabyAccess
from app.crud._baby_access_check import verify_baby_access
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
    """Return paginated feeding entries; requires accepted membership."""
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    base_filter = [FeedingEntry.baby_id == baby_id]
    if from_time:
        base_filter.append(FeedingEntry.timestamp >= from_time)
    if to_time:
        base_filter.append(FeedingEntry.timestamp <= to_time)

    count_result = await db.execute(
        select(func.count(FeedingEntry.id)).where(*base_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(FeedingEntry)
        .where(*base_filter)
        .order_by(FeedingEntry.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_feeding_entry_by_id(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
) -> FeedingEntry | None:
    """Get a feeding entry if the user has accepted access to its baby."""
    result = await db.execute(
        select(FeedingEntry)
        .join(BabyAccess, BabyAccess.baby_id == FeedingEntry.baby_id)
        .where(
            FeedingEntry.id == feeding_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_feeding_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    feeding_create: FeedingCreate,
    autocommit: bool = True,
) -> FeedingEntry | None:
    """Create a feeding entry; requires accepted membership."""
    if not await verify_baby_access(db, baby_id, user_id):
        return None

    feeding = FeedingEntry(
        baby_id=baby_id,
        feeding_type=feeding_create.feeding_type,
        amount_ml=feeding_create.amount_ml,
        duration_min=feeding_create.duration_min,
        timestamp=feeding_create.timestamp,
        notes=feeding_create.notes,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(feeding)
    if autocommit:
        await db.commit()
        await db.refresh(feeding)
    else:
        await db.flush()
    return feeding


async def update_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
    feeding_update: FeedingUpdate,
    is_owner: bool = False,
) -> FeedingEntry | None:
    """
    Update a feeding entry.

    - Owner (is_owner=True): can update any entry for the baby.
    - Caregiver: can only update entries they created.
    Returns None (→ 404/403 at route layer) if not permitted.
    """
    entry = await get_feeding_entry_by_id(db, feeding_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None  # caregiver cannot edit another person's entry

    for key, value in feeding_update.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    """Delete a feeding entry; owner can delete any, caregiver only their own."""
    entry = await get_feeding_entry_by_id(db, feeding_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(FeedingEntry).where(FeedingEntry.id == feeding_id))
    await db.commit()
    return True
