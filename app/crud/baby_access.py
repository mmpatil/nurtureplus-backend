from __future__ import annotations
"""CRUD operations for baby access / caregiver collaboration."""
import logging
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.baby_access import BabyAccess
from app.models.babies import Baby
from app.models.users import User

logger = logging.getLogger(__name__)

INVITE_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_baby(db: AsyncSession, baby_id: UUID) -> Baby | None:
    result = await db.execute(select(Baby).where(Baby.id == baby_id))
    return result.scalar_one_or_none()


async def _get_user(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Owner row creation (called when a baby is first created)
# ---------------------------------------------------------------------------

async def create_owner_membership(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> BabyAccess:
    """Create the owner BabyAccess row immediately when a baby is created."""
    existing = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.user_id == user_id,
            BabyAccess.role == "owner",
            BabyAccess.status == "accepted",
        )
    )
    owner_membership = existing.scalar_one_or_none()
    if owner_membership:
        return owner_membership

    access = BabyAccess(
        baby_id=baby_id,
        user_id=user_id,
        role="owner",
        status="accepted",
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(access)
    await db.commit()
    await db.refresh(access)
    logger.info(f"Owner membership created: baby={baby_id} user={user_id}")
    return access


# ---------------------------------------------------------------------------
# Caregiver list
# ---------------------------------------------------------------------------

async def get_caregivers_for_baby(
    db: AsyncSession,
    baby_id: UUID,
) -> dict:
    """
    Return all membership rows for a baby grouped by status.

    Returns:
        {
          "owner": BabyAccess | None,
          "caregivers": [BabyAccess],    # accepted caregivers
          "pending_invites": [BabyAccess],
        }
    """
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.status.in_(["accepted", "pending"]),
        ).order_by(BabyAccess.created_at)
    )
    rows = result.scalars().all()

    owner = None
    caregivers = []
    pending = []

    for row in rows:
        if row.role == "owner":
            owner = row
        elif row.status == "accepted":
            caregivers.append(row)
        elif row.status == "pending":
            pending.append(row)

    return {"owner": owner, "caregivers": caregivers, "pending_invites": pending}


# ---------------------------------------------------------------------------
# Invite creation
# ---------------------------------------------------------------------------

async def create_invite(
    db: AsyncSession,
    baby_id: UUID,
    invited_by_user_id: UUID,
    invite_email: str | None,
    role: str = "caregiver",
) -> tuple[BabyAccess, None] | tuple[None, str]:
    """
    Create a pending invite for a caregiver.

    Returns (invite, None) on success.
    Returns (None, error_message) on business-rule violation.
    """
    if role != "caregiver":
        return None, "Only 'caregiver' role can be invited"

    normalized_email = invite_email.lower().strip() if invite_email else None

    existing_user = None
    if normalized_email:
        existing_user_result = await db.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        existing_user = existing_user_result.scalar_one_or_none()

    duplicate_predicates = []
    if existing_user:
        duplicate_predicates.append(BabyAccess.user_id == existing_user.id)
    if normalized_email:
        duplicate_predicates.append(func.lower(BabyAccess.invite_email) == normalized_email)

    if duplicate_predicates:
        existing = await db.execute(
            select(BabyAccess).where(
                BabyAccess.baby_id == baby_id,
                BabyAccess.status.in_(["pending", "accepted"]),
                or_(*duplicate_predicates),
            )
        )
        if existing.scalar_one_or_none():
            return None, "This caregiver already has access or a pending invite"

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    invite = BabyAccess(
        baby_id=baby_id,
        user_id=None,               # filled on acceptance
        role=role,
        status="pending",
        invited_by_user_id=invited_by_user_id,
        invite_email=normalized_email,
        invite_token=token,
        invite_expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    logger.info(f"Invite created: baby={baby_id} email={invite_email} by={invited_by_user_id}")
    return invite, None


# ---------------------------------------------------------------------------
# Invite preview (unauthenticated)
# ---------------------------------------------------------------------------

async def get_invite_by_token(
    db: AsyncSession,
    token: str,
) -> BabyAccess | None:
    """Find a BabyAccess row by invite_token regardless of status."""
    result = await db.execute(
        select(BabyAccess).where(BabyAccess.invite_token == token)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Invite acceptance
# ---------------------------------------------------------------------------

async def accept_invite(
    db: AsyncSession,
    token: str,
    accepting_user_id: UUID,
) -> tuple[BabyAccess, None] | tuple[None, str]:
    """
    Accept a pending invite on behalf of accepting_user_id.

    Idempotent: if the same user already accepted this token, return the row.

    Returns (BabyAccess, None) on success.
    Returns (None, error_message) on failure.
    """
    invite = await get_invite_by_token(db, token)

    if invite is None:
        return None, "Invalid invite token"

    # Idempotent: already accepted by this user
    if invite.status == "accepted" and invite.user_id == accepting_user_id:
        return invite, None

    if invite.status == "revoked":
        return None, "This invite has been revoked"

    if invite.status == "accepted":
        return None, "This invite has already been accepted by another user"

    if invite.invite_expires_at and invite.invite_expires_at < datetime.now(timezone.utc):
        return None, "This invite has expired"

    # Check the user does not already have an accepted membership for this baby
    existing_result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == invite.baby_id,
            BabyAccess.user_id == accepting_user_id,
            BabyAccess.status == "accepted",
        )
    )
    existing_membership = existing_result.scalar_one_or_none()
    if existing_membership:
        if invite.status == "pending":
            invite.status = "revoked"
            invite.revoked_at = datetime.now(timezone.utc)
            await db.commit()
        return existing_membership, None

    invite.user_id = accepting_user_id
    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(invite)
    logger.info(f"Invite accepted: baby={invite.baby_id} user={accepting_user_id}")
    return invite, None


# ---------------------------------------------------------------------------
# Revoke invite
# ---------------------------------------------------------------------------

async def revoke_invite(
    db: AsyncSession,
    invite_id: UUID,
) -> BabyAccess | None:
    """
    Revoke a pending invite by id.
    Returns the updated row or None if not found / already accepted.
    """
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.id == invite_id,
            BabyAccess.status == "pending",
        )
    )
    invite = result.scalar_one_or_none()
    if not invite:
        return None

    invite.status = "revoked"
    invite.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invite)
    logger.info(f"Invite revoked: id={invite_id}")
    return invite


# ---------------------------------------------------------------------------
# Remove caregiver
# ---------------------------------------------------------------------------

async def remove_caregiver(
    db: AsyncSession,
    baby_id: UUID,
    caregiver_user_id: UUID,
) -> bool:
    """
    Revoke an accepted caregiver's access.
    Cannot remove the owner through this path.
    Returns True if removed, False if not found or is the owner.
    """
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.baby_id == baby_id,
            BabyAccess.user_id == caregiver_user_id,
            BabyAccess.role == "caregiver",
            BabyAccess.status == "accepted",
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        return False

    membership.status = "revoked"
    membership.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(f"Caregiver removed: baby={baby_id} user={caregiver_user_id}")
    return True


# ---------------------------------------------------------------------------
# Lookup by invite ID (for owner operations)
# ---------------------------------------------------------------------------

async def get_access_row_by_id(
    db: AsyncSession,
    access_id: UUID,
) -> BabyAccess | None:
    result = await db.execute(
        select(BabyAccess).where(
            BabyAccess.id == access_id,
        )
    )
    return result.scalar_one_or_none()
