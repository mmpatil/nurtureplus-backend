from __future__ import annotations
"""CRUD operations for babies — membership-aware."""
import logging
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.babies import Baby
from app.models.baby_access import BabyAccess
from app.models.users import User
from app.schemas.baby import BabyCreate, BabyUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_accepted_access(
    db: AsyncSession, baby_id: UUID, user_id: UUID
) -> BabyAccess | None:
    """Return the accepted BabyAccess row for (baby, user) or None."""
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# List babies (owned + shared)
# ---------------------------------------------------------------------------

async def get_babies_for_user(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    Return all babies accessible to the user (owner or accepted caregiver),
    each enriched with role/ownership metadata.

    Returns:
        Tuple of (list of enriched dicts, total count)
    """
    limit = min(limit, 100)
    offset = max(offset, 0)

    # Total count of distinct babies this user can access
    count_result = await db.execute(
        select(func.count(BabyAccess.id)).where(
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    total = count_result.scalar() or 0

    # Fetch all babies via the membership table (ordered newest first)
    result = await db.execute(
        select(Baby, BabyAccess)
        .join(BabyAccess, BabyAccess.baby_id == Baby.id)
        .where(
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
        .order_by(Baby.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()

    enriched = []
    for baby, access in rows:
        caregiver_count = await _get_caregiver_count(db, baby.id)
        owner_summary = await _get_owner_summary(db, baby.id)

        enriched.append({
            "baby": baby,
            "role": access.role,
            "caregiver_count": caregiver_count,
            "owner": owner_summary,
        })

    return enriched, total


async def _get_caregiver_count(db: AsyncSession, baby_id: UUID) -> int:
    """Count accepted caregivers for a baby (not counting the owner)."""
    result = await db.execute(
        select(func.count(BabyAccess.id)).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.role == "caregiver",
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar() or 0


async def _get_owner_summary(db: AsyncSession, baby_id: UUID) -> User | None:
    """Return the User row for the baby's owner."""
    result = await db.execute(
        select(User)
        .join(BabyAccess, BabyAccess.user_id == User.id)
        .where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.role == "owner",
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Get single baby (membership-aware)
# ---------------------------------------------------------------------------

async def get_baby_by_id(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> Baby | None:
    """
    Get a baby by ID, requiring an accepted membership for user_id.
    Returns None (→ 404) if user has no accepted access.
    """
    access = await _get_accepted_access(db, baby_id, user_id)
    if access is None:
        return None

    result = await db.execute(select(Baby).where(Baby.id == baby_id))
    return result.scalar_one_or_none()


async def get_baby_by_id_owner_only(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> Baby | None:
    """
    Like get_baby_by_id but restricted to the owner.
    Used for mutating the baby profile (update / delete).
    """
    result = await db.execute(
        select(Baby)
        .join(BabyAccess, BabyAccess.baby_id == Baby.id)
        .where(
            Baby.id == baby_id,
            BabyAccess.user_id == user_id,
            BabyAccess.role == "owner",
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Create baby
# ---------------------------------------------------------------------------

async def create_baby(
    db: AsyncSession,
    user_id: UUID,
    baby_create: BabyCreate,
) -> Baby:
    """
    Create a new baby and immediately create the owner membership row.
    """
    from app.crud.baby_access import create_owner_membership

    baby = Baby(
        user_id=user_id,
        name=baby_create.name,
        birth_date=baby_create.birth_date,
        photo_url=baby_create.photo_url,
    )
    db.add(baby)
    await db.flush()  # get baby.id without committing

    await create_owner_membership(db, baby.id, user_id)
    # create_owner_membership commits; refresh to get latest state
    await db.refresh(baby)
    logger.info(f"Created baby: {baby.id} for user: {user_id}")
    return baby


# ---------------------------------------------------------------------------
# Update baby (owner only)
# ---------------------------------------------------------------------------

async def update_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    baby_update: BabyUpdate,
) -> Baby | None:
    baby = await get_baby_by_id_owner_only(db, baby_id, user_id)
    if not baby:
        return None

    if baby_update.name is not None:
        baby.name = baby_update.name
    if baby_update.birth_date is not None:
        baby.birth_date = baby_update.birth_date
    if baby_update.photo_url is not None:
        baby.photo_url = baby_update.photo_url

    await db.commit()
    await db.refresh(baby)
    logger.info(f"Updated baby: {baby.id}")
    return baby


# ---------------------------------------------------------------------------
# Delete baby (owner only)
# ---------------------------------------------------------------------------

async def delete_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> bool:
    baby = await get_baby_by_id_owner_only(db, baby_id, user_id)
    if not baby:
        return False

    await db.execute(delete(Baby).where(Baby.id == baby_id))
    await db.commit()
    logger.info(f"Deleted baby: {baby_id} for user: {user_id}")
    return True
