from __future__ import annotations
"""API routes for Nurture+ backend."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from dateutil import parser as date_parser

from app.core.config import settings
from app.core.security import get_current_user, get_authenticated_identity
from app.core.access import (
    get_baby_access_for_user,
    check_baby_access,
    require_entry_edit_permission,
    require_baby_edit_permission,
    require_non_anonymous,
)
from app.db.session import get_db
from app.models.users import User
from app.models.baby_access import BabyAccess
from app.schemas.auth import SessionResponse
from app.schemas.account import AccountDeletionResponse
from app.schemas.baby import Baby, BabyCreate, BabyUpdate, BabyListResponse
from app.schemas.user import UserSummary
from app.schemas.caregiver import (
    CaregiverEntry,
    CaregiverListResponse,
    InviteCreate,
    InviteResponse,
    InvitePreview,
    InviteAcceptRequest,
)
from app.crud import babies as babies_crud
from app.crud import users as users_crud
from app.crud import feeding_entries as feeding_crud
from app.crud import diaper_entries as diaper_crud
from app.crud import sleep_entries as sleep_crud
from app.crud import mood_entries as mood_crud
from app.crud import recovery_entries as recovery_crud
from app.crud import growth_entries as growth_crud
from app.crud import milestone_entries as milestone_crud
from app.crud import baby_access as baby_access_crud
from app.crud import account_deletion as account_deletion_crud
from app.crud import food_intelligence as food_intelligence_crud
from app.crud import voice_logging as voice_logging_crud
from app.schemas.feeding import (
    Feeding,
    FeedingAnalysisRequest,
    FeedingAnalysisResponse,
    FeedingConfirmRequest,
    FeedingCreate,
    FeedingListResponse,
    FeedingMedia as FeedingMediaSchema,
    FeedingNutritionEstimate as FeedingNutritionEstimateSchema,
    FeedingOptionsResponse,
    FeedingUpdate,
)
from app.schemas.diaper import Diaper, DiaperCreate, DiaperUpdate, DiaperListResponse
from app.schemas.sleep import Sleep, SleepCreate, SleepUpdate, SleepListResponse
from app.schemas.food_profile import BabyFoodProfileResponse, BabyFoodProfileUpdate
from app.schemas.mood import Mood, MoodCreate, MoodUpdate, MoodListResponse
from app.schemas.product_analysis import ProductAnalysisRequest, ProductAnalysisResponse
from app.schemas.recovery import (
    RecoveryEntryCreate,
    RecoveryEntryResponse,
    RecoveryEntryUpdate,
    RecoveryEntryListResponse,
    RecoverySummaryResponse,
)
from app.models.feeding_entry import FeedingEntry
from app.models.feeding_nutrition_estimate import FeedingNutritionEstimate
from app.models.diaper_entry import DiaperEntry
from app.models.sleep_entry import SleepEntry
from app.models.babies import Baby as BabyModel
from app.models.recovery_entry import RecoveryEntry
from app.schemas.growth import Growth, GrowthCreate, GrowthUpdate, GrowthListResponse
from app.schemas.milestone import Milestone, MilestoneCreate, MilestoneUpdate, MilestoneListResponse
from app.schemas.voice import VoiceLogCreatedAction, VoiceLogDraftAction, VoiceLogRequest, VoiceLogResponse, VoiceLogType

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_uuid(value: str, label: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} format",
        )


def _parse_datetime(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid {label} date format",
        )


def _user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
    )


async def _resolve_user_summary(
    db: AsyncSession,
    user_id: UUID | None,
    cache: dict[UUID, UserSummary | None] | None = None,
) -> UserSummary | None:
    if user_id is None:
        return None
    if cache is not None and user_id in cache:
        return cache[user_id]

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    summary = _user_to_summary(user) if user else None
    if cache is not None:
        cache[user_id] = summary
    return summary


async def _serialize_baby(
    db: AsyncSession,
    baby: BabyModel,
    role: str,
) -> Baby:
    caregiver_count = await babies_crud._get_caregiver_count(db, baby.id)
    owner_user = await babies_crud._get_owner_summary(db, baby.id)
    return Baby(
        id=baby.id,
        user_id=baby.user_id,
        name=baby.name,
        birth_date=baby.birth_date,
        photo_url=baby.photo_url,
        created_at=baby.created_at,
        updated_at=baby.updated_at,
        current_user_role=role,
        ownership_type="owned" if role == "owner" else "shared",
        caregiver_count=caregiver_count,
        owner=_user_to_summary(owner_user) if owner_user else None,
    )


async def _serialize_entry_with_audit(
    db: AsyncSession,
    entry,
    schema_cls,
    cache: dict[UUID, UserSummary | None] | None = None,
):
    schema = schema_cls.model_validate(entry)
    update_payload = {
        "created_by": await _resolve_user_summary(
            db, getattr(entry, "created_by_user_id", None), cache
        ),
        "updated_by": await _resolve_user_summary(
            db, getattr(entry, "updated_by_user_id", None), cache
        ),
    }
    if schema_cls is Feeding and isinstance(entry, FeedingEntry):
        media = await feeding_crud.list_feeding_media(db, entry.id)
        nutrition_estimate = await feeding_crud.get_feeding_nutrition_estimate(db, entry.id)
        update_payload["media"] = [
            FeedingMediaSchema.model_validate(item) for item in media
        ]
        update_payload["nutrition_estimate"] = (
            FeedingNutritionEstimateSchema.model_validate(nutrition_estimate)
            if nutrition_estimate
            else None
        )
    return schema.model_copy(update=update_payload)


async def _serialize_entries_with_audit(
    db: AsyncSession,
    entries: list,
    schema_cls,
):
    cache: dict[UUID, UserSummary | None] = {}
    return [
        await _serialize_entry_with_audit(db, entry, schema_cls, cache)
        for entry in entries
    ]


VOICE_RESPONSE_SCHEMAS = {
    VoiceLogType.feeding: Feeding,
    VoiceLogType.diaper: Diaper,
    VoiceLogType.sleep: Sleep,
    VoiceLogType.mood: Mood,
    VoiceLogType.recovery: RecoveryEntryResponse,
    VoiceLogType.growth: Growth,
    VoiceLogType.milestone: Milestone,
}


async def _resolve_caregiver_entry(
    db: AsyncSession,
    row: BabyAccess,
) -> CaregiverEntry:
    """Build a CaregiverEntry, loading the linked User if available."""
    return CaregiverEntry(
        id=row.id,
        baby_id=row.baby_id,
        user_id=row.user_id,
        role=row.role,
        status=row.status,
        invite_email=row.invite_email,
        invite_expires_at=row.invite_expires_at,
        accepted_at=row.accepted_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        user=await _resolve_user_summary(db, row.user_id),
    )


# ---------------------------------------------------------------------------
# Health & Auth
# ---------------------------------------------------------------------------

@router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.post("/auth/session", tags=["auth"])
async def create_session(
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """
    Create or retrieve a user session.

    Verifies Firebase token (or dev bypass) and ensures a local user exists.
    Idempotent: multiple calls with the same token return the same user.
    """
    logger.info(
        f"Session endpoint - firebase_uid={current_user.firebase_uid}, "
        f"internal_id={current_user.id}"
    )
    return SessionResponse(
        user_id=str(current_user.id),
        firebase_uid=current_user.firebase_uid,
    )


@router.post("/voice/logs", tags=["voice"], response_model=VoiceLogResponse)
async def create_voice_logs(
    body: VoiceLogRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VoiceLogResponse:
    analysis = await voice_logging_crud.analyze_voice_transcript(
        transcript=body.transcript,
        baby_id=body.baby_id,
        timezone_name=body.timezone,
        client_now=body.client_now,
    )

    if analysis.requires_baby_access and body.baby_id is not None:
        await require_baby_edit_permission(db, body.baby_id, current_user)

    if not analysis.should_autosave:
        return VoiceLogResponse(
            status=analysis.status,
            message=analysis.message,
            draft_actions=[
                VoiceLogDraftAction(
                    log_type=action.log_type,
                    confidence=action.confidence,
                    payload=action.payload,
                    missing_fields=action.missing_fields,
                    warnings=action.warnings,
                )
                for action in analysis.actions
            ],
        )

    created = await voice_logging_crud.create_voice_logs(
        db=db,
        user_id=current_user.id,
        baby_id=body.baby_id,
        actions=analysis.actions,
    )
    return VoiceLogResponse(
        status="created",
        message=analysis.message,
        created_actions=[
            VoiceLogCreatedAction(
                log_type=created_action.log_type,
                confidence=created_action.confidence,
                resource=(
                    await _serialize_entry_with_audit(
                        db,
                        created_action.resource,
                        VOICE_RESPONSE_SCHEMAS[created_action.log_type],
                    )
                ).model_dump(mode="json"),
            )
            for created_action in created
        ],
    )


@router.delete("/account", tags=["auth"], response_model=AccountDeletionResponse)
async def delete_account(
    authorization: Optional[str] = Header(None),
    x_dev_uid: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> AccountDeletionResponse | JSONResponse:
    """
    Delete current user's account and associated data.

    Notes:
    - User identity is derived from verified auth token/header only.
    - Idempotent: deleting an already-removed local account still succeeds.
    - Returns structured success/failure payload for mobile clients.
    """
    try:
        identity = await get_authenticated_identity(authorization, x_dev_uid)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": "UNAUTHENTICATED",
                "message": str(exc.detail),
            },
        )

    auth_time: datetime | None = identity.get("auth_time")
    if not settings.dev_bypass_auth and auth_time is not None:
        max_age = timedelta(minutes=settings.account_delete_reauth_minutes)
        if datetime.now(timezone.utc) - auth_time > max_age:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "success": False,
                    "code": "REAUTH_REQUIRED",
                    "message": "Please sign in again before deleting your account.",
                },
            )

    result = await db.execute(
        select(User).where(User.firebase_uid == identity["firebase_uid"])
    )
    current_user = result.scalar_one_or_none()

    # Idempotent local deletion response (user row may already be gone).
    if current_user is None:
        try:
            account_deletion_crud.revoke_and_delete_auth_user(identity["firebase_uid"])
        except account_deletion_crud.AccountDeletionError as exc:
            logger.error(
                "Account delete partial failure (local already gone): uid=%s code=%s",
                identity["firebase_uid"],
                exc.code,
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "code": exc.code,
                    "message": exc.message,
                },
            )
        return AccountDeletionResponse(
            success=True,
            message="Your account and associated data have been deleted.",
        )

    try:
        local_result = await account_deletion_crud.delete_local_account_data(db, current_user)
        account_deletion_crud.revoke_and_delete_auth_user(current_user.firebase_uid)
        logger.info(
            "Account deleted for user_id=%s firebase_uid=%s owned_babies=%d storage_objects_deleted=%d",
            current_user.id,
            current_user.firebase_uid,
            len(local_result.owned_baby_ids),
            local_result.storage_objects_deleted,
        )
        return AccountDeletionResponse(
            success=True,
            message="Your account and associated data have been deleted.",
        )
    except account_deletion_crud.AccountDeletionError as exc:
        logger.error(
            "Account deletion failed for user_id=%s firebase_uid=%s code=%s",
            current_user.id,
            current_user.firebase_uid,
            exc.code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected account deletion failure for user_id=%s", current_user.id)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "code": "DELETION_FAILED",
                "message": "Account deletion failed. Please try again.",
            },
        )


# ---------------------------------------------------------------------------
# Babies
# ---------------------------------------------------------------------------

@router.get("/babies", tags=["babies"], response_model=BabyListResponse)
async def list_babies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> BabyListResponse:
    """
    List all babies accessible to the current user (owned + shared),
    each annotated with the user's role and caregiver count.
    """
    enriched_list, total = await babies_crud.get_babies_for_user(
        db, current_user.id, limit=limit, offset=offset
    )

    items = []
    for item in enriched_list:
        baby = item["baby"]
        role = item["role"]
        items.append(await _serialize_baby(db, baby, role))

    return BabyListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/babies", tags=["babies"], response_model=Baby, status_code=status.HTTP_201_CREATED)
async def create_baby(
    baby_create: BabyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """Create a new baby for the current user (creates owner membership automatically)."""
    baby = await babies_crud.create_baby(db, current_user.id, baby_create)
    return await _serialize_baby(db, baby, "owner")


@router.get("/babies/{baby_id}", tags=["babies"], response_model=Baby)
async def get_baby(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """Get a specific baby by ID (requires any accepted membership)."""
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    access = await check_baby_access(db, baby_uuid, current_user.id)

    result = await db.execute(select(BabyModel).where(BabyModel.id == baby_uuid))
    baby = result.scalar_one_or_none()
    if not baby:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")

    return await _serialize_baby(db, baby, access.role)


@router.put("/babies/{baby_id}", tags=["babies"], response_model=Baby)
async def update_baby(
    baby_id: str,
    baby_update: BabyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """Update a baby's information (owner only)."""
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    access = await check_baby_access(db, baby_uuid, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can update the baby profile",
        )
    baby = await babies_crud.update_baby(db, baby_uuid, current_user.id, baby_update)
    if not baby:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_baby(db, baby, "owner")


@router.delete("/babies/{baby_id}", tags=["babies"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_baby(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a baby (owner only)."""
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    access = await check_baby_access(db, baby_uuid, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can delete the baby profile",
        )
    deleted = await babies_crud.delete_baby(db, baby_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return None


# ---------------------------------------------------------------------------
# Caregiver / invite endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/caregivers", tags=["caregivers"], response_model=CaregiverListResponse)
async def list_caregivers(
    baby_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaregiverListResponse:
    """
    List all caregivers and pending invites for a baby.
    Requires owner access.
    """
    access = await check_baby_access(db, baby_id, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can view caregiver list",
        )

    groups = await baby_access_crud.get_caregivers_for_baby(db, baby_id)

    owner_entry = await _resolve_caregiver_entry(db, groups["owner"]) if groups["owner"] else None
    caregiver_entries = [
        await _resolve_caregiver_entry(db, row) for row in groups["caregivers"]
    ]
    pending_entries = [
        await _resolve_caregiver_entry(db, row) for row in groups["pending_invites"]
    ]

    return CaregiverListResponse(
        owner=owner_entry,
        caregivers=caregiver_entries,
        pending_invites=pending_entries,
    )


@router.post(
    "/babies/{baby_id}/caregivers/invite",
    tags=["caregivers"],
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    baby_id: UUID,
    body: InviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteResponse:
    """
    Create a caregiver invite for a baby.
    Only the owner can invite; generates a secure one-time token valid 7 days.
    """
    require_non_anonymous(current_user)
    access = await check_baby_access(db, baby_id, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can invite caregivers",
        )

    if body.role != "caregiver":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only 'caregiver' role can be invited",
        )

    invite, error = await baby_access_crud.create_invite(
        db,
        baby_id=baby_id,
        invited_by_user_id=current_user.id,
        invite_email=body.invite_email,
        role=body.role,
    )
    if error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error)

    return InviteResponse(
        id=invite.id,
        baby_id=invite.baby_id,
        role=invite.role,
        status=invite.status,
        invite_email=invite.invite_email,
        invite_token=invite.invite_token,
        share_code=invite.invite_token,
        invite_expires_at=invite.invite_expires_at,
    )


@router.get("/babies/invites/{token}", tags=["caregivers"], response_model=InvitePreview)
async def preview_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePreview:
    """
    Preview an invite by token — no authentication required.
    Returns baby/inviter summary and whether the invite is still valid.
    """
    invite = await baby_access_crud.get_invite_by_token(db, token)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    # Load baby name
    result = await db.execute(select(BabyModel).where(BabyModel.id == invite.baby_id))
    baby = result.scalar_one_or_none()
    if not baby:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")

    # Load inviter
    inviter_summary = None
    if invite.invited_by_user_id:
        result = await db.execute(
            select(User).where(User.id == invite.invited_by_user_id)
        )
        inviter = result.scalar_one_or_none()
        if inviter:
            inviter_summary = _user_to_summary(inviter)

    is_valid = (
        invite.status == "pending"
        and (invite.invite_expires_at is None or invite.invite_expires_at > datetime.now(timezone.utc))
    )
    is_expired = (
        invite.invite_expires_at is not None
        and invite.invite_expires_at <= datetime.now(timezone.utc)
    )

    return InvitePreview(
        baby_id=baby.id,
        baby_name=baby.name,
        inviter=inviter_summary,
        role=invite.role,
        status=invite.status,
        invite_email=invite.invite_email,
        expires_at=invite.invite_expires_at,
        is_valid=is_valid,
        is_expired=is_expired,
    )


@router.post("/babies/invites/accept", tags=["caregivers"], response_model=CaregiverEntry)
async def accept_invite(
    body: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaregiverEntry:
    """
    Accept an invite using the one-time token.
    The user must be authenticated and must not have an anonymous Firebase account.
    """
    require_non_anonymous(current_user)

    membership, error = await baby_access_crud.accept_invite(
        db, token=body.token, accepting_user_id=current_user.id
    )
    if error:
        status_code = status.HTTP_400_BAD_REQUEST
        if error == "Invalid invite token":
            status_code = status.HTTP_404_NOT_FOUND
        elif error in {"This invite has expired", "This invite has been revoked"}:
            status_code = status.HTTP_410_GONE
        raise HTTPException(
            status_code=status_code,
            detail=error,
        )

    return await _resolve_caregiver_entry(db, membership)


@router.post(
    "/babies/invites/{invite_id}/revoke",
    tags=["caregivers"],
    response_model=CaregiverEntry,
)
async def revoke_invite(
    invite_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaregiverEntry:
    """Revoke a pending invite (owner only)."""
    invite = await baby_access_crud.get_access_row_by_id(db, invite_id)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite not found",
        )

    access = await check_baby_access(db, invite.baby_id, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can revoke invites",
        )

    revoked_invite = await baby_access_crud.revoke_invite(db, invite_id=invite_id)
    if not revoked_invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found",
        )

    return await _resolve_caregiver_entry(db, revoked_invite)


@router.delete(
    "/babies/{baby_id}/caregivers/{caregiver_user_id}",
    tags=["caregivers"],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_caregiver(
    baby_id: UUID,
    caregiver_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a caregiver from a baby (owner only). Cannot remove the owner."""
    access = await check_baby_access(db, baby_id, current_user.id)
    if access.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the baby's owner can remove caregivers",
        )

    if caregiver_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot remove themselves",
        )

    removed = await baby_access_crud.remove_caregiver(db, baby_id=baby_id, caregiver_user_id=caregiver_user_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caregiver not found")

    return None


# ---------------------------------------------------------------------------
# Feeding Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/feeding-options", tags=["feedings"], response_model=FeedingOptionsResponse)
async def get_feeding_options(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedingOptionsResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await check_baby_access(db, baby_uuid, current_user.id)
    options = await feeding_crud.get_feeding_options_for_baby(db, baby_uuid, current_user.id)
    if options is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return FeedingOptionsResponse(
        baby_id=baby_uuid,
        age_months=options.age_months,
        age_band=options.age_band,
        options=options.options,
    )


@router.get("/babies/{baby_id}/food-profile", tags=["feedings"], response_model=BabyFoodProfileResponse)
async def get_baby_food_profile(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BabyFoodProfileResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await check_baby_access(db, baby_uuid, current_user.id)
    return await food_intelligence_crud.get_baby_food_profile(db, baby_uuid)


@router.put("/babies/{baby_id}/food-profile", tags=["feedings"], response_model=BabyFoodProfileResponse)
async def update_baby_food_profile(
    baby_id: str,
    body: BabyFoodProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BabyFoodProfileResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    return await food_intelligence_crud.update_baby_food_profile(db, baby_uuid, body)


@router.get("/babies/{baby_id}/feedings", tags=["feedings"], response_model=FeedingListResponse)
async def list_feedings(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    to_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
) -> FeedingListResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    from_dt = _parse_datetime(from_time, "from_time")
    to_dt = _parse_datetime(to_time, "to_time")

    entries, total = await feeding_crud.get_feeding_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset,
        from_time=from_dt, to_time=to_dt,
    )

    if total == 0:
        # Distinguish "no entries" from "no access"
        await check_baby_access(db, baby_uuid, current_user.id)

    return FeedingListResponse(
        items=await _serialize_entries_with_audit(db, entries, Feeding),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/feedings", tags=["feedings"], response_model=Feeding, status_code=status.HTTP_201_CREATED)
async def create_feeding(
    baby_id: str,
    feeding_create: FeedingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feeding:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    feeding = await feeding_crud.create_feeding_entry(db, baby_uuid, current_user.id, feeding_create)
    if not feeding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, feeding, Feeding)


@router.post(
    "/babies/{baby_id}/feedings/analyze",
    tags=["feedings"],
    response_model=FeedingAnalysisResponse,
)
async def analyze_feeding(
    baby_id: str,
    body: FeedingAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedingAnalysisResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    try:
        return await food_intelligence_crud.analyze_feeding(db, baby_uuid, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post(
    "/babies/{baby_id}/feedings/confirm",
    tags=["feedings"],
    response_model=Feeding,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_feeding_analysis(
    baby_id: str,
    body: FeedingConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feeding:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    try:
        return await food_intelligence_crud.confirm_feeding_analysis(
            db,
            baby_uuid,
            current_user.id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.put("/feedings/{feeding_id}", tags=["feedings"], response_model=Feeding)
async def update_feeding(
    feeding_id: str,
    feeding_update: FeedingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feeding:
    feeding_uuid = _parse_uuid(feeding_id, "feeding ID")
    # Determine if user is owner so CRUD can apply correct permission
    entry = await feeding_crud.get_feeding_entry_by_id(db, feeding_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    feeding = await feeding_crud.update_feeding_entry(
        db, feeding_uuid, current_user.id, feeding_update,
        is_owner=(access.role == "owner"),
    )
    if not feeding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")
    return await _serialize_entry_with_audit(db, feeding, Feeding)


@router.delete("/feedings/{feeding_id}", tags=["feedings"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_feeding(
    feeding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feeding_uuid = _parse_uuid(feeding_id, "feeding ID")
    entry = await feeding_crud.get_feeding_entry_by_id(db, feeding_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await feeding_crud.delete_feeding_entry(
        db, feeding_uuid, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")
    return None


@router.post("/food-products/analyze", tags=["feedings"], response_model=ProductAnalysisResponse)
async def analyze_food_product(
    body: ProductAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductAnalysisResponse:
    try:
        return await food_intelligence_crud.analyze_product(db, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Diaper Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/diapers", tags=["diapers"], response_model=DiaperListResponse)
async def list_diapers(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
) -> DiaperListResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    from_dt = _parse_datetime(from_time, "from_time")
    to_dt = _parse_datetime(to_time, "to_time")

    entries, total = await diaper_crud.get_diaper_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset,
        from_time=from_dt, to_time=to_dt,
    )

    if total == 0:
        await check_baby_access(db, baby_uuid, current_user.id)

    return DiaperListResponse(
        items=await _serialize_entries_with_audit(db, entries, Diaper),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/diapers", tags=["diapers"], response_model=Diaper, status_code=status.HTTP_201_CREATED)
async def create_diaper(
    baby_id: str,
    diaper_create: DiaperCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Diaper:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    diaper = await diaper_crud.create_diaper_entry(db, baby_uuid, current_user.id, diaper_create)
    if not diaper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, diaper, Diaper)


@router.put("/diapers/{diaper_id}", tags=["diapers"], response_model=Diaper)
async def update_diaper(
    diaper_id: str,
    diaper_update: DiaperUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Diaper:
    diaper_uuid = _parse_uuid(diaper_id, "diaper ID")
    entry = await diaper_crud.get_diaper_entry_by_id(db, diaper_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    diaper = await diaper_crud.update_diaper_entry(
        db, diaper_uuid, current_user.id, diaper_update,
        is_owner=(access.role == "owner"),
    )
    if not diaper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")
    return await _serialize_entry_with_audit(db, diaper, Diaper)


@router.delete("/diapers/{diaper_id}", tags=["diapers"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_diaper(
    diaper_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    diaper_uuid = _parse_uuid(diaper_id, "diaper ID")
    entry = await diaper_crud.get_diaper_entry_by_id(db, diaper_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await diaper_crud.delete_diaper_entry(
        db, diaper_uuid, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")
    return None


# ---------------------------------------------------------------------------
# Sleep Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/sleep", tags=["sleep"], response_model=SleepListResponse)
async def list_sleep(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
) -> SleepListResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    from_dt = _parse_datetime(from_time, "from_time")
    to_dt = _parse_datetime(to_time, "to_time")

    entries, total = await sleep_crud.get_sleep_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset,
        from_time=from_dt, to_time=to_dt,
    )

    if total == 0:
        await check_baby_access(db, baby_uuid, current_user.id)

    return SleepListResponse(
        items=await _serialize_entries_with_audit(db, entries, Sleep),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/sleep", tags=["sleep"], response_model=Sleep, status_code=status.HTTP_201_CREATED)
async def create_sleep(
    baby_id: str,
    sleep_create: SleepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Sleep:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    sleep = await sleep_crud.create_sleep_entry(db, baby_uuid, current_user.id, sleep_create)
    if not sleep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, sleep, Sleep)


@router.put("/sleep/{sleep_id}", tags=["sleep"], response_model=Sleep)
async def update_sleep(
    sleep_id: str,
    sleep_update: SleepUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Sleep:
    sleep_uuid = _parse_uuid(sleep_id, "sleep ID")
    entry = await sleep_crud.get_sleep_entry_by_id(db, sleep_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    sleep = await sleep_crud.update_sleep_entry(
        db, sleep_uuid, current_user.id, sleep_update,
        is_owner=(access.role == "owner"),
    )
    if not sleep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")
    return await _serialize_entry_with_audit(db, sleep, Sleep)


@router.delete("/sleep/{sleep_id}", tags=["sleep"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_sleep(
    sleep_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sleep_uuid = _parse_uuid(sleep_id, "sleep ID")
    entry = await sleep_crud.get_sleep_entry_by_id(db, sleep_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await sleep_crud.delete_sleep_entry(
        db, sleep_uuid, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")
    return None


# ---------------------------------------------------------------------------
# Mood Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/moods", tags=["moods"], response_model=MoodListResponse)
async def list_moods(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
) -> MoodListResponse:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    from_dt = _parse_datetime(from_time, "from_time")
    to_dt = _parse_datetime(to_time, "to_time")

    entries, total = await mood_crud.get_mood_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset,
        from_time=from_dt, to_time=to_dt,
    )

    if total == 0:
        await check_baby_access(db, baby_uuid, current_user.id)

    return MoodListResponse(
        items=await _serialize_entries_with_audit(db, entries, Mood),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/moods", tags=["moods"], response_model=Mood, status_code=status.HTTP_201_CREATED)
async def create_mood(
    baby_id: str,
    mood_create: MoodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Mood:
    baby_uuid = _parse_uuid(baby_id, "baby ID")
    await require_baby_edit_permission(db, baby_uuid, current_user)
    mood = await mood_crud.create_mood_entry(db, baby_uuid, current_user.id, mood_create)
    if not mood:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, mood, Mood)


@router.put("/moods/{mood_id}", tags=["moods"], response_model=Mood)
async def update_mood(
    mood_id: str,
    mood_update: MoodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Mood:
    mood_uuid = _parse_uuid(mood_id, "mood ID")
    entry = await mood_crud.get_mood_entry_by_id(db, mood_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    mood = await mood_crud.update_mood_entry(
        db, mood_uuid, current_user.id, mood_update,
        is_owner=(access.role == "owner"),
    )
    if not mood:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")
    return await _serialize_entry_with_audit(db, mood, Mood)


@router.delete("/moods/{mood_id}", tags=["moods"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_mood(
    mood_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mood_uuid = _parse_uuid(mood_id, "mood ID")
    entry = await mood_crud.get_mood_entry_by_id(db, mood_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await mood_crud.delete_mood_entry(
        db, mood_uuid, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")
    return None


# ---------------------------------------------------------------------------
# Recovery Endpoints (user-scoped, not baby-scoped — unchanged)
# ---------------------------------------------------------------------------

@router.post("/recovery", tags=["recovery"], response_model=RecoveryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_recovery_entry(
    recovery_create: RecoveryEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    entry = await recovery_crud.create_recovery_entry(db, current_user.id, recovery_create)
    return await _serialize_entry_with_audit(db, entry, RecoveryEntryResponse)


@router.get("/recovery", tags=["recovery"], response_model=RecoveryEntryListResponse)
async def list_recovery_entries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
) -> RecoveryEntryListResponse:
    from_dt = _parse_datetime(from_time, "from_time")
    to_dt = _parse_datetime(to_time, "to_time")

    entries, total = await recovery_crud.list_recovery_entries(
        db, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )

    return RecoveryEntryListResponse(
        items=await _serialize_entries_with_audit(db, entries, RecoveryEntryResponse),
        total=total, limit=limit, offset=offset,
    )


@router.get("/recovery/latest", tags=["recovery"], response_model=Optional[RecoveryEntryResponse])
async def get_latest_recovery_entry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[RecoveryEntryResponse]:
    entry = await recovery_crud.get_latest_recovery_entry(db, current_user.id)
    if entry:
        return await _serialize_entry_with_audit(db, entry, RecoveryEntryResponse)
    return None


@router.get("/recovery/summary", tags=["recovery"], response_model=RecoverySummaryResponse)
async def get_recovery_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(7, ge=1, le=365),
) -> RecoverySummaryResponse:
    summary_data = await recovery_crud.get_recovery_summary(db, current_user.id, days=days)
    response = RecoverySummaryResponse(
        days=summary_data["days"],
        average_water_intake_oz=summary_data["average_water_intake_oz"],
        check_in_count=summary_data["check_in_count"],
    )
    if summary_data["latest_entry"]:
        response.latest_entry = await _serialize_entry_with_audit(
            db, summary_data["latest_entry"], RecoveryEntryResponse
        )
    return response


@router.get("/recovery/{entry_id}", tags=["recovery"], response_model=RecoveryEntryResponse)
async def get_recovery_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    entry_uuid = _parse_uuid(entry_id, "entry ID")
    entry = await recovery_crud.get_recovery_entry(db, entry_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")
    return await _serialize_entry_with_audit(db, entry, RecoveryEntryResponse)


@router.put("/recovery/{entry_id}", tags=["recovery"], response_model=RecoveryEntryResponse)
async def update_recovery_entry(
    entry_id: str,
    recovery_update: RecoveryEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    entry_uuid = _parse_uuid(entry_id, "entry ID")
    entry = await recovery_crud.update_recovery_entry(db, entry_uuid, current_user.id, recovery_update)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")
    return await _serialize_entry_with_audit(db, entry, RecoveryEntryResponse)


@router.delete("/recovery/{entry_id}", tags=["recovery"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_recovery_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry_uuid = _parse_uuid(entry_id, "entry ID")
    deleted = await recovery_crud.delete_recovery_entry(db, entry_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")
    return None


# ---------------------------------------------------------------------------
# Analytics Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/analytics/summary", tags=["analytics"])
async def get_analytics_summary(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    range_days: int = Query(7, ge=1, le=365),
):
    """Get analytics summary for a baby (owner or caregiver can call this)."""
    baby_uuid = _parse_uuid(baby_id, "baby ID")

    # Verify access (raises 404 if no membership)
    await check_baby_access(db, baby_uuid, current_user.id)

    now_utc = datetime.now(timezone.utc)
    start_date = now_utc - timedelta(days=range_days)

    feeding_result = await db.execute(
        select(
            func.date(FeedingEntry.timestamp).label("date"),
            func.count(FeedingEntry.id).label("count"),
        ).where(
            FeedingEntry.baby_id == baby_uuid,
            FeedingEntry.timestamp >= start_date,
        ).group_by(func.date(FeedingEntry.timestamp))
        .order_by(func.date(FeedingEntry.timestamp))
    )
    feeding_by_day = [{"date": str(row[0]), "count": row[1]} for row in feeding_result.all()]

    diaper_result = await db.execute(
        select(
            func.date(DiaperEntry.timestamp).label("date"),
            func.count(DiaperEntry.id).label("count"),
        ).where(
            DiaperEntry.baby_id == baby_uuid,
            DiaperEntry.timestamp >= start_date,
        ).group_by(func.date(DiaperEntry.timestamp))
        .order_by(func.date(DiaperEntry.timestamp))
    )
    diaper_by_day = [{"date": str(row[0]), "count": row[1]} for row in diaper_result.all()]

    sleep_result = await db.execute(
        select(
            func.date(SleepEntry.start_time).label("date"),
            func.sum(SleepEntry.duration_min).label("total_minutes"),
        ).where(
            SleepEntry.baby_id == baby_uuid,
            SleepEntry.start_time >= start_date,
            SleepEntry.duration_min.isnot(None),
        ).group_by(func.date(SleepEntry.start_time))
        .order_by(func.date(SleepEntry.start_time))
    )
    sleep_by_day = [
        {"date": str(row[0]), "hours": round(row[1] / 60.0, 1) if row[1] else 0}
        for row in sleep_result.all()
    ]

    total_feedings = (await db.execute(
        select(func.count(FeedingEntry.id)).where(
            FeedingEntry.baby_id == baby_uuid,
            FeedingEntry.timestamp >= start_date,
        )
    )).scalar() or 0

    total_diapers = (await db.execute(
        select(func.count(DiaperEntry.id)).where(
            DiaperEntry.baby_id == baby_uuid,
            DiaperEntry.timestamp >= start_date,
        )
    )).scalar() or 0

    total_sleep_minutes = (await db.execute(
        select(func.sum(SleepEntry.duration_min)).where(
            SleepEntry.baby_id == baby_uuid,
            SleepEntry.start_time >= start_date,
            SleepEntry.duration_min.isnot(None),
        )
    )).scalar() or 0

    avg_sleep_hours = round(total_sleep_minutes / 60.0 / max(range_days, 1), 1)

    nutrition_totals_result = await db.execute(
        select(
            func.coalesce(func.sum(FeedingNutritionEstimate.calories), 0),
            func.coalesce(func.sum(FeedingNutritionEstimate.protein_g), 0),
            func.coalesce(func.sum(FeedingNutritionEstimate.iron_mg), 0),
            func.coalesce(func.sum(FeedingNutritionEstimate.calcium_mg), 0),
            func.count(FeedingNutritionEstimate.id),
        )
        .join(FeedingEntry, FeedingEntry.id == FeedingNutritionEstimate.feeding_id)
        .where(
            FeedingNutritionEstimate.baby_id == baby_uuid,
            FeedingEntry.timestamp >= start_date,
        )
    )
    calories_total, protein_total, iron_total, calcium_total, analyzed_feedings = (
        nutrition_totals_result.one()
    )

    return {
        "rangeDays": range_days,
        "feedingCountByDay": feeding_by_day,
        "diaperCountByDay": diaper_by_day,
        "sleepHoursByDay": sleep_by_day,
        "totals": {
            "feedings": total_feedings,
            "diapers": total_diapers,
            "avgSleepHoursPerDay": avg_sleep_hours,
        },
        "nutritionTotals": {
            "calories": round(float(calories_total or 0), 2),
            "protein_g": round(float(protein_total or 0), 2),
            "iron_mg": round(float(iron_total or 0), 2),
            "calcium_mg": round(float(calcium_total or 0), 2),
            "analyzedFeedings": int(analyzed_feedings or 0),
        },
    }


# ---------------------------------------------------------------------------
# Growth Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/growth", tags=["growth"], response_model=GrowthListResponse)
async def list_growth_entries(
    baby_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> GrowthListResponse:
    entries, total = await growth_crud.get_growth_entries_for_baby(
        db, baby_id, current_user.id, limit=limit, offset=offset
    )
    if total == 0:
        await check_baby_access(db, baby_id, current_user.id)
    return GrowthListResponse(
        items=await _serialize_entries_with_audit(db, entries, Growth),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/growth", tags=["growth"], response_model=Growth, status_code=status.HTTP_201_CREATED)
async def create_growth_entry(
    baby_id: UUID,
    body: GrowthCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Growth:
    await require_baby_edit_permission(db, baby_id, current_user)
    entry = await growth_crud.create_growth_entry(db, baby_id, current_user.id, body)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, entry, Growth)


@router.put("/growth/{growth_id}", tags=["growth"], response_model=Growth)
async def update_growth_entry(
    growth_id: UUID,
    body: GrowthUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Growth:
    entry = await growth_crud.get_growth_entry_by_id(db, growth_id, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growth entry not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    updated = await growth_crud.update_growth_entry(
        db, growth_id, current_user.id, body, is_owner=(access.role == "owner")
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growth entry not found")
    return await _serialize_entry_with_audit(db, updated, Growth)


@router.delete("/growth/{growth_id}", tags=["growth"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_growth_entry(
    growth_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = await growth_crud.get_growth_entry_by_id(db, growth_id, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growth entry not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await growth_crud.delete_growth_entry(
        db, growth_id, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growth entry not found")


# ---------------------------------------------------------------------------
# Milestones Endpoints
# ---------------------------------------------------------------------------

@router.get("/babies/{baby_id}/milestones", tags=["milestones"], response_model=MilestoneListResponse)
async def list_milestone_entries(
    baby_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> MilestoneListResponse:
    entries, total = await milestone_crud.get_milestone_entries_for_baby(
        db, baby_id, current_user.id, limit=limit, offset=offset
    )
    if total == 0:
        await check_baby_access(db, baby_id, current_user.id)
    return MilestoneListResponse(
        items=await _serialize_entries_with_audit(db, entries, Milestone),
        total=total, limit=limit, offset=offset,
    )


@router.post("/babies/{baby_id}/milestones", tags=["milestones"], response_model=Milestone, status_code=status.HTTP_201_CREATED)
async def create_milestone_entry(
    baby_id: UUID,
    body: MilestoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Milestone:
    await require_baby_edit_permission(db, baby_id, current_user)
    entry = await milestone_crud.create_milestone_entry(db, baby_id, current_user.id, body)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    return await _serialize_entry_with_audit(db, entry, Milestone)


@router.put("/milestones/{milestone_id}", tags=["milestones"], response_model=Milestone)
async def update_milestone_entry(
    milestone_id: UUID,
    body: MilestoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Milestone:
    entry = await milestone_crud.get_milestone_entry_by_id(db, milestone_id, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone entry not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    updated = await milestone_crud.update_milestone_entry(
        db, milestone_id, current_user.id, body, is_owner=(access.role == "owner")
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone entry not found")
    return await _serialize_entry_with_audit(db, updated, Milestone)


@router.delete("/milestones/{milestone_id}", tags=["milestones"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_milestone_entry(
    milestone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = await milestone_crud.get_milestone_entry_by_id(db, milestone_id, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone entry not found")

    access = await get_baby_access_for_user(db, entry.baby_id, current_user.id)
    require_entry_edit_permission(entry.created_by_user_id, access, current_user)

    deleted = await milestone_crud.delete_milestone_entry(
        db, milestone_id, current_user.id, is_owner=(access.role == "owner")
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone entry not found")
