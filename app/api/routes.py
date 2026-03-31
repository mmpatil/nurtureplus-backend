"""API routes for Nurture+ backend."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from dateutil import parser as date_parser

from app.core.security import get_current_user, verify_firebase_token
from app.db.session import get_db
from app.models.users import User
from app.schemas.auth import SessionResponse
from app.schemas.baby import Baby, BabyCreate, BabyUpdate, BabyListResponse
from app.crud import babies as babies_crud
from app.crud import users as users_crud
from app.crud import feeding_entries as feeding_crud
from app.crud import diaper_entries as diaper_crud
from app.crud import sleep_entries as sleep_crud
from app.crud import mood_entries as mood_crud
from app.crud import recovery_entries as recovery_crud
from app.schemas.feeding import Feeding, FeedingCreate, FeedingUpdate, FeedingListResponse
from app.schemas.diaper import Diaper, DiaperCreate, DiaperUpdate, DiaperListResponse
from app.schemas.sleep import Sleep, SleepCreate, SleepUpdate, SleepListResponse
from app.schemas.mood import Mood, MoodCreate, MoodUpdate, MoodListResponse
from app.schemas.recovery import (
    RecoveryEntryCreate,
    RecoveryEntryResponse,
    RecoveryEntryUpdate,
    RecoveryEntryListResponse,
    RecoverySummaryResponse,
)
from app.models.feeding_entry import FeedingEntry
from app.models.diaper_entry import DiaperEntry
from app.models.sleep_entry import SleepEntry
from app.models.mood_entry import MoodEntry
from app.models.babies import Baby as BabyModel
from app.models.recovery_entry import RecoveryEntry

logger = logging.getLogger(__name__)

router = APIRouter()


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
    
    **Headers:**
    - `Authorization: Bearer <firebase_id_token>` - Firebase ID token
    - `X-Dev-Uid: <user_id>` - Dev bypass (only if DEV_BYPASS_AUTH=true)
    
    **Request Flow:**
    1. Extracts Bearer token from Authorization header
    2. Verifies token signature with Firebase Admin SDK
    3. Extracts firebase_uid from decoded token
    4. Finds or creates User in database with that firebase_uid
    5. Returns both internal user_id (UUID) and firebase_uid
    
    **Responses:**
    - 200: Session created/retrieved (returns user_id + firebase_uid)
    - 401: Missing or invalid token
    - 500: Database error
    
    **Response Fields:**
    - `user_id`: Internal database UUID (for all subsequent API calls)
    - `firebase_uid`: Firebase UID (for reference, from decoded token)
    """
    logger.info(
        f"Session endpoint - firebase_uid={current_user.firebase_uid}, internal_id={current_user.id}"
    )
    
    return SessionResponse(
        user_id=str(current_user.id),
        firebase_uid=current_user.firebase_uid,
    )


# ============================================================================
# Babies Endpoints
# ============================================================================


@router.get("/babies", tags=["babies"], response_model=BabyListResponse)
async def list_babies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> BabyListResponse:
    """
    List all babies for the authenticated user with pagination.
    
    **Query Parameters:**
    - `limit`: Items per page (1-100, default 20)
    - `offset`: Items to skip (default 0)
    
    **Responses:**
    - 200: List of babies with pagination info
    - 401: Unauthorized
    """
    babies, total = await babies_crud.get_babies_for_user(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    
    return BabyListResponse(
        items=[
            Baby.model_validate(baby) for baby in babies
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/babies", tags=["babies"], response_model=Baby, status_code=status.HTTP_201_CREATED)
async def create_baby(
    baby_create: BabyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """
    Create a new baby for the authenticated user.
    
    **Request Body:**
    - `name` (string, required): Baby name (1-100 chars)
    - `birth_date` (date, required): Birth date in YYYY-MM-DD format
    - `photo_url` (string, optional): Photo URL (max 500 chars)
    
    **Responses:**
    - 201: Baby created
    - 401: Unauthorized
    - 422: Validation error
    """
    baby = await babies_crud.create_baby(
        db,
        current_user.id,
        baby_create,
    )
    
    return Baby.model_validate(baby)


@router.get("/babies/{baby_id}", tags=["babies"], response_model=Baby)
async def get_baby(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """
    Get a specific baby by ID.
    
    **Path Parameters:**
    - `baby_id` (UUID): Baby ID
    
    **Responses:**
    - 200: Baby details
    - 401: Unauthorized
    - 404: Baby not found or doesn't belong to user
    """
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid baby ID format",
        )
    
    baby = await babies_crud.get_baby_by_id(db, baby_uuid, current_user.id)
    
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )
    
    return Baby.model_validate(baby)


@router.put("/babies/{baby_id}", tags=["babies"], response_model=Baby)
async def update_baby(
    baby_id: str,
    baby_update: BabyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Baby:
    """
    Update a baby's information.
    
    **Path Parameters:**
    - `baby_id` (UUID): Baby ID
    
    **Request Body:**
    - `name` (string, optional): Baby name
    - `birth_date` (date, optional): Birth date in YYYY-MM-DD format
    - `photo_url` (string, optional): Photo URL
    
    **Responses:**
    - 200: Baby updated
    - 401: Unauthorized
    - 404: Baby not found
    - 422: Validation error
    """
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid baby ID format",
        )
    
    baby = await babies_crud.update_baby(
        db,
        baby_uuid,
        current_user.id,
        baby_update,
    )
    
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )
    
    return Baby.model_validate(baby)


@router.delete("/babies/{baby_id}", tags=["babies"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_baby(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a baby.
    
    **Path Parameters:**
    - `baby_id` (UUID): Baby ID
    
    **Responses:**
    - 204: Baby deleted
    - 401: Unauthorized
    - 404: Baby not found
    """
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid baby ID format",
        )
    
    deleted = await babies_crud.delete_baby(
        db,
        baby_uuid,
        current_user.id,
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found",
        )
    
    return None


# ============================================================================
# Feeding Endpoints
# ============================================================================


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
    """List feeding entries for a baby with optional time range filter."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    from_dt = None
    to_dt = None
    try:
        if from_time:
            from_dt = date_parser.isoparse(from_time)
        if to_time:
            to_dt = date_parser.isoparse(to_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")
    
    entries, total = await feeding_crud.get_feeding_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )
    
    if total == 0:
        # Check if baby exists and belongs to user
        baby_result = await db.execute(
            select(BabyModel).where((BabyModel.id == baby_uuid) & (BabyModel.user_id == current_user.id))
        )
        if not baby_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return FeedingListResponse(
        items=[Feeding.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/babies/{baby_id}/feedings", tags=["feedings"], response_model=Feeding, status_code=status.HTTP_201_CREATED)
async def create_feeding(
    baby_id: str,
    feeding_create: FeedingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feeding:
    """Create a feeding entry for a baby."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    feeding = await feeding_crud.create_feeding_entry(db, baby_uuid, current_user.id, feeding_create)
    if not feeding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return Feeding.model_validate(feeding)


@router.put("/feedings/{feeding_id}", tags=["feedings"], response_model=Feeding)
async def update_feeding(
    feeding_id: str,
    feeding_update: FeedingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feeding:
    """Update a feeding entry."""
    try:
        feeding_uuid = UUID(feeding_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid feeding ID")
    
    feeding = await feeding_crud.update_feeding_entry(db, feeding_uuid, current_user.id, feeding_update)
    if not feeding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")
    
    return Feeding.model_validate(feeding)


@router.delete("/feedings/{feeding_id}", tags=["feedings"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_feeding(
    feeding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a feeding entry."""
    try:
        feeding_uuid = UUID(feeding_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid feeding ID")
    
    deleted = await feeding_crud.delete_feeding_entry(db, feeding_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feeding not found")
    
    return None


# ============================================================================
# Diaper Endpoints
# ============================================================================


@router.get("/babies/{baby_id}/diapers", tags=["diapers"], response_model=DiaperListResponse)
async def list_diapers(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    to_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
) -> DiaperListResponse:
    """List diaper entries for a baby with optional time range filter."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    from_dt = None
    to_dt = None
    try:
        if from_time:
            from_dt = date_parser.isoparse(from_time)
        if to_time:
            to_dt = date_parser.isoparse(to_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")
    
    entries, total = await diaper_crud.get_diaper_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )
    
    if total == 0:
        baby_result = await db.execute(
            select(BabyModel).where((BabyModel.id == baby_uuid) & (BabyModel.user_id == current_user.id))
        )
        if not baby_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return DiaperListResponse(
        items=[Diaper.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/babies/{baby_id}/diapers", tags=["diapers"], response_model=Diaper, status_code=status.HTTP_201_CREATED)
async def create_diaper(
    baby_id: str,
    diaper_create: DiaperCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Diaper:
    """Create a diaper entry for a baby."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    diaper = await diaper_crud.create_diaper_entry(db, baby_uuid, current_user.id, diaper_create)
    if not diaper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return Diaper.model_validate(diaper)


@router.put("/diapers/{diaper_id}", tags=["diapers"], response_model=Diaper)
async def update_diaper(
    diaper_id: str,
    diaper_update: DiaperUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Diaper:
    """Update a diaper entry."""
    try:
        diaper_uuid = UUID(diaper_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid diaper ID")
    
    diaper = await diaper_crud.update_diaper_entry(db, diaper_uuid, current_user.id, diaper_update)
    if not diaper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")
    
    return Diaper.model_validate(diaper)


@router.delete("/diapers/{diaper_id}", tags=["diapers"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_diaper(
    diaper_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a diaper entry."""
    try:
        diaper_uuid = UUID(diaper_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid diaper ID")
    
    deleted = await diaper_crud.delete_diaper_entry(db, diaper_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diaper not found")
    
    return None


# ============================================================================
# Sleep Endpoints
# ============================================================================


@router.get("/babies/{baby_id}/sleep", tags=["sleep"], response_model=SleepListResponse)
async def list_sleep(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    to_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
) -> SleepListResponse:
    """List sleep entries for a baby with optional time range filter."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    from_dt = None
    to_dt = None
    try:
        if from_time:
            from_dt = date_parser.isoparse(from_time)
        if to_time:
            to_dt = date_parser.isoparse(to_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")
    
    entries, total = await sleep_crud.get_sleep_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )
    
    if total == 0:
        baby_result = await db.execute(
            select(BabyModel).where((BabyModel.id == baby_uuid) & (BabyModel.user_id == current_user.id))
        )
        if not baby_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return SleepListResponse(
        items=[Sleep.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/babies/{baby_id}/sleep", tags=["sleep"], response_model=Sleep, status_code=status.HTTP_201_CREATED)
async def create_sleep(
    baby_id: str,
    sleep_create: SleepCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Sleep:
    """Create a sleep entry for a baby."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    sleep = await sleep_crud.create_sleep_entry(db, baby_uuid, current_user.id, sleep_create)
    if not sleep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return Sleep.model_validate(sleep)


@router.put("/sleep/{sleep_id}", tags=["sleep"], response_model=Sleep)
async def update_sleep(
    sleep_id: str,
    sleep_update: SleepUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Sleep:
    """Update a sleep entry."""
    try:
        sleep_uuid = UUID(sleep_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sleep ID")
    
    sleep = await sleep_crud.update_sleep_entry(db, sleep_uuid, current_user.id, sleep_update)
    if not sleep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")
    
    return Sleep.model_validate(sleep)


@router.delete("/sleep/{sleep_id}", tags=["sleep"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_sleep(
    sleep_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sleep entry."""
    try:
        sleep_uuid = UUID(sleep_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid sleep ID")
    
    deleted = await sleep_crud.delete_sleep_entry(db, sleep_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sleep not found")
    
    return None


# ============================================================================
# Mood Endpoints
# ============================================================================


@router.get("/babies/{baby_id}/moods", tags=["moods"], response_model=MoodListResponse)
async def list_moods(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    to_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
) -> MoodListResponse:
    """List mood entries for a baby with optional time range filter."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    from_dt = None
    to_dt = None
    try:
        if from_time:
            from_dt = date_parser.isoparse(from_time)
        if to_time:
            to_dt = date_parser.isoparse(to_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")
    
    entries, total = await mood_crud.get_mood_entries_for_baby(
        db, baby_uuid, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )
    
    if total == 0:
        baby_result = await db.execute(
            select(BabyModel).where((BabyModel.id == baby_uuid) & (BabyModel.user_id == current_user.id))
        )
        if not baby_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return MoodListResponse(
        items=[Mood.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/babies/{baby_id}/moods", tags=["moods"], response_model=Mood, status_code=status.HTTP_201_CREATED)
async def create_mood(
    baby_id: str,
    mood_create: MoodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Mood:
    """Create a mood entry for a baby."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    mood = await mood_crud.create_mood_entry(db, baby_uuid, current_user.id, mood_create)
    if not mood:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    return Mood.model_validate(mood)


@router.put("/moods/{mood_id}", tags=["moods"], response_model=Mood)
async def update_mood(
    mood_id: str,
    mood_update: MoodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Mood:
    """Update a mood entry."""
    try:
        mood_uuid = UUID(mood_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid mood ID")
    
    mood = await mood_crud.update_mood_entry(db, mood_uuid, current_user.id, mood_update)
    if not mood:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")
    
    return Mood.model_validate(mood)


@router.delete("/moods/{mood_id}", tags=["moods"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_mood(
    mood_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a mood entry."""
    try:
        mood_uuid = UUID(mood_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid mood ID")
    
    deleted = await mood_crud.delete_mood_entry(db, mood_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mood not found")
    
    return None


# ============================================================================
# Recovery Endpoints (User/Mother Postpartum Recovery Tracking)
# ============================================================================


@router.post("/recovery", tags=["recovery"], response_model=RecoveryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_recovery_entry(
    recovery_create: RecoveryEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    """Create a new recovery entry for the authenticated user."""
    entry = await recovery_crud.create_recovery_entry(db, current_user.id, recovery_create)
    return RecoveryEntryResponse.model_validate(entry)


@router.get("/recovery", tags=["recovery"], response_model=RecoveryEntryListResponse)
async def list_recovery_entries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    to_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
) -> RecoveryEntryListResponse:
    """List recovery entries for the authenticated user, newest first."""
    from_dt = None
    to_dt = None
    try:
        if from_time:
            from_dt = date_parser.isoparse(from_time)
        if to_time:
            to_dt = date_parser.isoparse(to_time)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date format")

    entries, total = await recovery_crud.list_recovery_entries(
        db, current_user.id, limit=limit, offset=offset, from_time=from_dt, to_time=to_dt
    )

    return RecoveryEntryListResponse(
        items=[RecoveryEntryResponse.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/recovery/latest", tags=["recovery"], response_model=Optional[RecoveryEntryResponse])
async def get_latest_recovery_entry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[RecoveryEntryResponse]:
    """Get the most recent recovery entry for the authenticated user."""
    entry = await recovery_crud.get_latest_recovery_entry(db, current_user.id)
    if entry:
        return RecoveryEntryResponse.model_validate(entry)
    return None


@router.get("/recovery/summary", tags=["recovery"], response_model=RecoverySummaryResponse)
async def get_recovery_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(7, ge=1, le=365, description="Number of days to summarize"),
) -> RecoverySummaryResponse:
    """Get recovery summary for the authenticated user over the specified number of days."""
    summary_data = await recovery_crud.get_recovery_summary(db, current_user.id, days=days)
    
    response = RecoverySummaryResponse(
        days=summary_data["days"],
        average_water_intake_oz=summary_data["average_water_intake_oz"],
        check_in_count=summary_data["check_in_count"],
    )
    
    if summary_data["latest_entry"]:
        response.latest_entry = RecoveryEntryResponse.model_validate(summary_data["latest_entry"])
    
    return response


@router.get("/recovery/{entry_id}", tags=["recovery"], response_model=RecoveryEntryResponse)
async def get_recovery_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    """Get a recovery entry by ID for the authenticated user."""
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid entry ID")

    entry = await recovery_crud.get_recovery_entry(db, entry_uuid, current_user.id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")

    return RecoveryEntryResponse.model_validate(entry)


@router.put("/recovery/{entry_id}", tags=["recovery"], response_model=RecoveryEntryResponse)
async def update_recovery_entry(
    entry_id: str,
    recovery_update: RecoveryEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecoveryEntryResponse:
    """Update a recovery entry for the authenticated user."""
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid entry ID")

    entry = await recovery_crud.update_recovery_entry(db, entry_uuid, current_user.id, recovery_update)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")

    return RecoveryEntryResponse.model_validate(entry)


@router.delete("/recovery/{entry_id}", tags=["recovery"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_recovery_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a recovery entry for the authenticated user."""
    try:
        entry_uuid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid entry ID")

    deleted = await recovery_crud.delete_recovery_entry(db, entry_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recovery entry not found")

    return None


# ============================================================================
# Analytics Endpoints
# ============================================================================


@router.get("/babies/{baby_id}/analytics/summary", tags=["analytics"])
async def get_analytics_summary(
    baby_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    range_days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
):
    """Get analytics summary for a baby including feeding, diaper, and sleep stats."""
    try:
        baby_uuid = UUID(baby_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid baby ID")
    
    # Verify baby belongs to user
    baby_result = await db.execute(
        select(BabyModel).where((BabyModel.id == baby_uuid) & (BabyModel.user_id == current_user.id))
    )
    if not baby_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baby not found")
    
    # Calculate date range in UTC
    now_utc = datetime.now(timezone.utc)
    start_date = now_utc - timedelta(days=range_days)
    
    # Get feeding data grouped by date
    feeding_result = await db.execute(
        select(
            func.date(FeedingEntry.timestamp).label('date'),
            func.count(FeedingEntry.id).label('count')
        ).where(
            (FeedingEntry.baby_id == baby_uuid) &
            (FeedingEntry.timestamp >= start_date)
        ).group_by(func.date(FeedingEntry.timestamp)).order_by(func.date(FeedingEntry.timestamp))
    )
    feeding_by_day = [{"date": str(row[0]), "count": row[1]} for row in feeding_result.all()]
    
    # Get diaper data grouped by date
    diaper_result = await db.execute(
        select(
            func.date(DiaperEntry.timestamp).label('date'),
            func.count(DiaperEntry.id).label('count')
        ).where(
            (DiaperEntry.baby_id == baby_uuid) &
            (DiaperEntry.timestamp >= start_date)
        ).group_by(func.date(DiaperEntry.timestamp)).order_by(func.date(DiaperEntry.timestamp))
    )
    diaper_by_day = [{"date": str(row[0]), "count": row[1]} for row in diaper_result.all()]
    
    # Get sleep data grouped by date (sum duration_min and convert to hours)
    sleep_result = await db.execute(
        select(
            func.date(SleepEntry.start_time).label('date'),
            func.sum(SleepEntry.duration_min).label('total_minutes')
        ).where(
            (SleepEntry.baby_id == baby_uuid) &
            (SleepEntry.start_time >= start_date) &
            (SleepEntry.duration_min.isnot(None))
        ).group_by(func.date(SleepEntry.start_time)).order_by(func.date(SleepEntry.start_time))
    )
    sleep_by_day = [
        {"date": str(row[0]), "hours": round(row[1] / 60.0, 1) if row[1] else 0}
        for row in sleep_result.all()
    ]
    
    # Calculate totals
    total_feedings = await db.execute(
        select(func.count(FeedingEntry.id)).where(
            (FeedingEntry.baby_id == baby_uuid) &
            (FeedingEntry.timestamp >= start_date)
        )
    )
    total_feedings = total_feedings.scalar() or 0
    
    total_diapers = await db.execute(
        select(func.count(DiaperEntry.id)).where(
            (DiaperEntry.baby_id == baby_uuid) &
            (DiaperEntry.timestamp >= start_date)
        )
    )
    total_diapers = total_diapers.scalar() or 0
    
    total_sleep_minutes = await db.execute(
        select(func.sum(SleepEntry.duration_min)).where(
            (SleepEntry.baby_id == baby_uuid) &
            (SleepEntry.start_time >= start_date) &
            (SleepEntry.duration_min.isnot(None))
        )
    )
    total_sleep_minutes = total_sleep_minutes.scalar() or 0
    avg_sleep_hours = round(total_sleep_minutes / 60.0 / max(range_days, 1), 1)
    
    return {
        "rangeDays": range_days,
        "feedingCountByDay": feeding_by_day,
        "diaperCountByDay": diaper_by_day,
        "sleepHoursByDay": sleep_by_day,
        "totals": {
            "feedings": total_feedings,
            "diapers": total_diapers,
            "avgSleepHoursPerDay": avg_sleep_hours,
        }
    }
