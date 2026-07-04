from __future__ import annotations
"""Reusable access checks for community groups."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.group_membership import GroupMembership
from app.models.users import User


def require_group_account(user: User) -> None:
    """Groups are limited to permanent authenticated accounts."""
    if user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Groups require a permanent (non-anonymous) account",
        )


def require_platform_admin(user: User) -> None:
    """Raise if the current user is not a platform administrator."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required",
        )


async def get_group_membership_for_user(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> GroupMembership | None:
    """Return the membership row for the user in the given group, if any."""
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def require_group_member_or_admin(
    db: AsyncSession,
    group_id: UUID,
    current_user: User,
) -> GroupMembership | None:
    """
    Require an active membership unless the current user is an admin.

    Returns the active membership row for members, or ``None`` for admins.
    """
    group_result = await db.execute(select(Group.id).where(Group.id == group_id))
    if group_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    if current_user.is_admin:
        return None

    membership = await get_group_membership_for_user(db, group_id, current_user.id)
    if membership is None or membership.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active group members can access this resource",
        )
    return membership
