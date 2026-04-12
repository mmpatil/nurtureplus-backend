"""CRUD operations for growth entries."""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.growth_entry import GrowthEntry
from app.schemas.growth import GrowthCreate, GrowthUpdate

logger = logging.getLogger(__name__)


async def _verify_baby_ownership(db: AsyncSession, baby_id: UUID, user_id: UUID) -> bool:
    from app.models.babies import Baby
    result = await db.execute(
        select(Baby).where((Baby.id == baby_id) & (Baby.user_id == user_id))
    )
    return result.scalar_one_or_none() is not None


async def get_growth_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[GrowthEntry], int]:
    if not await _verify_baby_ownership(db, baby_id, user_id):
        return [], 0

    count_result = await db.execute(
        select(func.count(GrowthEntry.id)).where(GrowthEntry.baby_id == baby_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(GrowthEntry)
        .where(GrowthEntry.baby_id == baby_id)
        .order_by(GrowthEntry.measurement_date.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_growth_entry_by_id(
    db: AsyncSession,
    growth_id: UUID,
    user_id: UUID,
) -> GrowthEntry | None:
    from app.models.babies import Baby
    result = await db.execute(
        select(GrowthEntry).join(Baby).where(
            (GrowthEntry.id == growth_id) & (Baby.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def create_growth_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    growth_create: GrowthCreate,
) -> GrowthEntry | None:
    if not await _verify_baby_ownership(db, baby_id, user_id):
        return None

    entry = GrowthEntry(
        baby_id=baby_id,
        measurement_date=growth_create.measurement_date,
        weight_kg=growth_create.weight_kg,
        height_cm=growth_create.height_cm,
        head_circumference_cm=growth_create.head_circumference_cm,
        notes=growth_create.notes,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_growth_entry(
    db: AsyncSession,
    growth_id: UUID,
    user_id: UUID,
    growth_update: GrowthUpdate,
) -> GrowthEntry | None:
    entry = await get_growth_entry_by_id(db, growth_id, user_id)
    if not entry:
        return None

    for key, value in growth_update.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_growth_entry(
    db: AsyncSession,
    growth_id: UUID,
    user_id: UUID,
) -> bool:
    entry = await get_growth_entry_by_id(db, growth_id, user_id)
    if not entry:
        return False
    await db.execute(delete(GrowthEntry).where(GrowthEntry.id == growth_id))
    await db.commit()
    return True
