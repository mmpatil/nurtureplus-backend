from __future__ import annotations
"""Account deletion orchestration helpers."""

import logging
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import unquote, urlparse
from uuid import UUID

from firebase_admin import auth, storage
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.babies import Baby
from app.models.feeding_media import FeedingMedia
from app.models.milestone_entry import MilestoneEntry
from app.models.product_analysis import ProductAnalysis
from app.models.users import User

logger = logging.getLogger(__name__)

# Local SQL tables that are removed directly or through FK cascades when the user row is deleted.
ACCOUNT_DATA_TABLES = [
    "users",
    "babies",
    "baby_access",
    "group_memberships",
    "group_messages",
    "group_message_attachments",
    "group_requests",
    "group_request_tags",
    "feeding_entries",
    "feeding_media",
    "feeding_nutrition_estimates",
    "diaper_entries",
    "sleep_entries",
    "mood_entries",
    "growth_entries",
    "milestone_entries",
    "recovery_entries",
    "baby_food_profiles",
    "product_analyses",
    "product_suitability_assessments",
]


@dataclass
class AccountDeletionResult:
    """Summary of deletion work for logging/diagnostics."""

    owned_baby_ids: list[UUID]
    storage_objects_deleted: int


class AccountDeletionError(Exception):
    """Raised when account deletion fails."""

    def __init__(self, code: str, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


async def _get_owned_baby_ids(db: AsyncSession, user_id: UUID) -> list[UUID]:
    result = await db.execute(select(Baby.id).where(Baby.user_id == user_id))
    return list(result.scalars().all())


async def _get_storage_urls_for_owned_data(
    db: AsyncSession,
    owned_baby_ids: Iterable[UUID],
) -> list[str]:
    baby_ids = list(owned_baby_ids)
    if not baby_ids:
        return []

    baby_result = await db.execute(
        select(Baby.photo_url).where(
            Baby.id.in_(baby_ids),  # noqa: SIM118
            Baby.photo_url.is_not(None),
        )
    )
    milestone_result = await db.execute(
        select(MilestoneEntry.photo_url).where(
            MilestoneEntry.baby_id.in_(baby_ids),  # noqa: SIM118
            MilestoneEntry.photo_url.is_not(None),
        )
    )
    feeding_media_result = await db.execute(
        select(FeedingMedia.media_url).where(
            FeedingMedia.baby_id.in_(baby_ids),  # noqa: SIM118
            FeedingMedia.media_url.is_not(None),
        )
    )

    urls: list[str] = []
    for value in baby_result.scalars().all():
        if value:
            urls.append(value)
    for value in milestone_result.scalars().all():
        if value:
            urls.append(value)
    for value in feeding_media_result.scalars().all():
        if value:
            urls.append(value)
    return urls


async def _get_storage_urls_for_user_analyses(
    db: AsyncSession,
    user_id: UUID,
) -> list[str]:
    result = await db.execute(
        select(ProductAnalysis.package_front_url, ProductAnalysis.package_back_url).where(
            ProductAnalysis.user_id == user_id
        )
    )
    urls: list[str] = []
    rows = result.all() if hasattr(result, "all") else []
    for front_url, back_url in rows:
        if front_url:
            urls.append(front_url)
        if back_url:
            urls.append(back_url)
    return urls


def _parse_storage_path_from_url(url: str) -> tuple[str | None, str] | None:
    """
    Parse Firebase Storage object path from a URL.

    Supports:
      - gs://bucket/path/to/object
      - https://firebasestorage.googleapis.com/v0/b/<bucket>/o/<encoded-object>
    """
    if url.startswith("gs://"):
        without_scheme = url.removeprefix("gs://")
        parts = without_scheme.split("/", 1)
        if len(parts) != 2:
            return None
        bucket_name, object_path = parts
        return bucket_name, object_path

    parsed = urlparse(url)
    if "firebasestorage.googleapis.com" not in parsed.netloc:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    # Format: /v0/b/<bucket>/o/<object path>
    try:
        bucket_index = path_parts.index("b")
        object_index = path_parts.index("o")
        bucket_name = path_parts[bucket_index + 1]
        encoded_object = "/".join(path_parts[object_index + 1 :])
        object_path = unquote(encoded_object)
        if not bucket_name or not object_path:
            return None
        return bucket_name, object_path
    except (ValueError, IndexError):
        return None


def _candidate_storage_prefixes(firebase_uid: str, owned_baby_ids: Iterable[UUID]) -> list[str]:
    prefixes = [
        f"users/{firebase_uid}/",
        f"user_uploads/{firebase_uid}/",
        f"uploads/users/{firebase_uid}/",
    ]
    for baby_id in owned_baby_ids:
        baby_id_str = str(baby_id)
        prefixes.extend(
            [
                f"babies/{baby_id_str}/",
                f"baby/{baby_id_str}/",
                f"uploads/babies/{baby_id_str}/",
            ]
        )
    return prefixes


def _safe_delete_blob(bucket_name: str | None, object_path: str) -> bool:
    try:
        bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()
        blob = bucket.blob(object_path)
        blob.delete()
        return True
    except Exception as exc:  # noqa: BLE001
        # Missing files are expected in idempotent retries.
        message = str(exc).lower()
        if "not found" in message or "404" in message:
            return False
        raise


def _delete_storage_data(
    firebase_uid: str,
    owned_baby_ids: Iterable[UUID],
    storage_urls: Iterable[str],
) -> int:
    """
    Best-effort Firebase Storage cleanup.

    Deletes:
      - object prefixes commonly keyed by user or owned baby IDs
      - direct file references found in persisted photo_url fields
    """
    deleted_count = 0

    for prefix in _candidate_storage_prefixes(firebase_uid, owned_baby_ids):
        try:
            bucket = storage.bucket()
            for blob in bucket.list_blobs(prefix=prefix):
                try:
                    blob.delete()
                    deleted_count += 1
                except Exception as exc:  # noqa: BLE001
                    message = str(exc).lower()
                    if "not found" in message or "404" in message:
                        continue
                    raise
        except Exception as exc:  # noqa: BLE001
            # No configured default bucket is non-fatal for environments
            # that do not use Firebase Storage.
            message = str(exc).lower()
            missing_default_bucket = (
                "default bucket name not specified" in message
                or "bucket name not specified" in message
                or "storage bucket" in message and "not configured" in message
            )
            if missing_default_bucket:
                logger.warning(
                    "Storage prefix cleanup skipped for prefix '%s': %s",
                    prefix,
                    exc,
                )
                continue
            raise

    parsed_paths = [_parse_storage_path_from_url(url) for url in storage_urls]
    for parsed in parsed_paths:
        if not parsed:
            continue
        bucket_name, object_path = parsed
        try:
            if _safe_delete_blob(bucket_name, object_path):
                deleted_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed deleting storage object '%s': %s", object_path, exc)
            raise

    return deleted_count


def revoke_and_delete_auth_user(firebase_uid: str) -> None:
    """Revoke sessions and delete Firebase Authentication user (idempotent)."""
    try:
        auth.revoke_refresh_tokens(firebase_uid)
    except auth.UserNotFoundError:
        logger.info("Firebase user already absent while revoking tokens: uid=%s", firebase_uid)
    except Exception as exc:  # noqa: BLE001
        raise AccountDeletionError(
            code="AUTH_REVOKE_FAILED",
            message="Failed to revoke active sessions.",
        ) from exc

    try:
        auth.delete_user(firebase_uid)
    except auth.UserNotFoundError:
        logger.info("Firebase user already deleted: uid=%s", firebase_uid)
    except Exception as exc:  # noqa: BLE001
        raise AccountDeletionError(
            code="AUTH_DELETE_FAILED",
            message="Failed to delete authentication account.",
        ) from exc


async def delete_local_account_data(
    db: AsyncSession,
    user: User,
) -> AccountDeletionResult:
    """
    Delete all SQL-backed user data and owned-baby scoped data.

    A delete on the users row cascades into babies, logs, and collaborations
    via FK rules (`ondelete`).
    """
    owned_baby_ids = await _get_owned_baby_ids(db, user.id)
    storage_urls = await _get_storage_urls_for_owned_data(db, owned_baby_ids)
    storage_urls.extend(await _get_storage_urls_for_user_analyses(db, user.id))

    try:
        deleted_storage_count = _delete_storage_data(
            firebase_uid=user.firebase_uid,
            owned_baby_ids=owned_baby_ids,
            storage_urls=storage_urls,
        )
    except Exception as exc:  # noqa: BLE001
        raise AccountDeletionError(
            code="STORAGE_DELETE_FAILED",
            message="Failed to delete one or more uploaded files.",
        ) from exc

    result = await db.execute(delete(User).where(User.id == user.id))
    if result.rowcount == 0:
        await db.rollback()
        raise AccountDeletionError(
            code="ACCOUNT_NOT_FOUND",
            message="Account was not found.",
            status_code=404,
        )

    await db.commit()
    return AccountDeletionResult(
        owned_baby_ids=owned_baby_ids,
        storage_objects_deleted=deleted_storage_count,
    )
