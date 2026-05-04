from __future__ import annotations
"""
Shared helper used by all baby-entry CRUD modules.

Centralises the "does this user have accepted access to this baby?" query
so each CRUD file doesn't need to duplicate the join.
"""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.baby_access import BabyAccess


async def verify_baby_access(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> BabyAccess | None:
    """
    Return the accepted BabyAccess row if user_id has access, else None.
    Used by entry CRUDs to gate create/list operations.
    """
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def verify_baby_access_by_entry_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> BabyAccess | None:
    """Alias for clarity when called from entry-level CRUD."""
    return await verify_baby_access(db, baby_id, user_id)
