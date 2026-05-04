from __future__ import annotations
"""
Reusable FastAPI dependencies for baby-scoped access control.

Access rules
------------
- owner   : full CRUD on the baby profile and all its entries
- caregiver: read + create entries; edit/delete only their own entries
- pending / revoked: no access (404 returned to avoid leaking existence)
- anonymous Firebase users: cannot accept invites or be granted access
"""
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.baby_access import BabyAccess
from app.models.users import User


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

async def get_baby_access_for_user(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> BabyAccess | None:
    """
    Return the BabyAccess row for this (baby, user) pair if it is accepted.
    Returns None if there is no accepted membership.
    """
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def check_baby_access(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> BabyAccess:
    """
    Like get_baby_access_for_user but raises HTTP 404 on failure.
    Callers get back the BabyAccess object, which carries the user's role.
    """
    access = await get_baby_access_for_user(db, baby_id, user_id)
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )
    return access


# ---------------------------------------------------------------------------
# FastAPI dependency factories
# ---------------------------------------------------------------------------

def require_baby_access(baby_id_param: str = "baby_id"):
    """
    Dependency factory: verifies the current user has *any* accepted access
    (owner or caregiver) to the baby identified by ``baby_id_param``.

    Returns the BabyAccess row so the caller can inspect the role.

    Usage::

        @router.get("/babies/{baby_id}/feedings")
        async def list_feedings(
            access: BabyAccess = Depends(require_baby_access()),
            ...
        ):
            ...
    """
    async def _dep(
        baby_id: UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> BabyAccess:
        return await check_baby_access(db, baby_id, current_user.id)

    return _dep


def require_baby_owner(baby_id_param: str = "baby_id"):
    """
    Dependency factory: verifies the current user is the *owner* of the baby.

    Used for mutating the baby profile itself and for invite management.
    """
    async def _dep(
        baby_id: UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> BabyAccess:
        access = await check_baby_access(db, baby_id, current_user.id)
        if access.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the baby's owner can perform this action",
            )
        return access

    return _dep


async def require_baby_edit_permission(
    db: AsyncSession,
    baby_id: UUID,
    current_user: User,
) -> BabyAccess:
    """
    Return accepted access for create/edit operations scoped to a baby.

    For the current MVP both owners and accepted caregivers can create baby
    entries, so this is equivalent to requiring accepted access.
    """
    return await check_baby_access(db, baby_id, current_user.id)


# ---------------------------------------------------------------------------
# Entry-level permission check
# ---------------------------------------------------------------------------

def require_entry_edit_permission(
    entry_or_created_by_user_id,
    access: BabyAccess,
    current_user: User,
) -> None:
    """
    Raises HTTP 403 if the user is not allowed to edit/delete this entry.

    Rules:
    - owner can edit/delete any entry for that baby
    - caregiver can only edit/delete entries they personally created
    """
    entry_created_by_user_id = getattr(
        entry_or_created_by_user_id,
        "created_by_user_id",
        entry_or_created_by_user_id,
    )
    if access.role == "owner":
        return
    # Caregiver path
    if entry_created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caregivers can only edit or delete entries they created",
        )


def require_non_anonymous(user: User) -> None:
    """Raises HTTP 403 if the user's Firebase identity is anonymous."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shared access requires a permanent (non-anonymous) account",
        )
