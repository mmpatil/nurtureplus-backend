from __future__ import annotations
"""Firestore helpers for Groups realtime chat mirroring."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import firebase_admin
from firebase_admin import firestore

from app.core.security import init_firebase
from app.models.group_membership import GroupMembership
from app.models.users import User
from app.schemas.group import GroupMessage as GroupMessageSchema

logger = logging.getLogger(__name__)

_FIRESTORE_CLIENT = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _group_ref(db_client, group_id: UUID | str):
    return db_client.collection("groups").document(str(group_id))


def _member_ref(db_client, group_id: UUID | str, firebase_uid: str):
    return _group_ref(db_client, group_id).collection("members").document(firebase_uid)


def _message_ref(db_client, group_id: UUID | str, message_id: UUID | str):
    return _group_ref(db_client, group_id).collection("messages").document(str(message_id))


def _group_state_ref(db_client, firebase_uid: str, group_id: UUID | str):
    return (
        db_client.collection("users")
        .document(firebase_uid)
        .collection("group_states")
        .document(str(group_id))
    )


def get_firestore_client():
    """Return a reusable Firestore client, or ``None`` if Firebase is unavailable."""
    global _FIRESTORE_CLIENT

    if _FIRESTORE_CLIENT is not None:
        return _FIRESTORE_CLIENT

    init_firebase()
    if not firebase_admin._apps:
        return None

    try:
        _FIRESTORE_CLIENT = firestore.client()
        return _FIRESTORE_CLIENT
    except Exception:  # noqa: BLE001
        logger.exception("Failed to initialize Firestore client for Groups sync")
        return None


async def upsert_group_member(user: User, membership: GroupMembership) -> bool:
    """Upsert the active group member document."""
    if not user.firebase_uid:
        return False

    client = get_firestore_client()
    if client is None:
        return False

    payload = {
        "firebase_uid": user.firebase_uid,
        "user_id": str(user.id),
        "status": "active",
        "is_admin": bool(user.is_admin),
        "joined_at": _isoformat(membership.joined_at or _utcnow()),
    }

    def _write():
        _member_ref(client, membership.group_id, user.firebase_uid).set(payload, merge=True)

    await asyncio.to_thread(_write)
    return True


async def delete_group_member(group_id: UUID, firebase_uid: str | None) -> bool:
    """Delete a group member document."""
    if not firebase_uid:
        return False

    client = get_firestore_client()
    if client is None:
        return False

    await asyncio.to_thread(
        lambda: _member_ref(client, group_id, firebase_uid).delete()
    )
    return True


async def delete_group_members(group_id: UUID, firebase_uids: list[str]) -> bool:
    """Delete multiple group member documents."""
    if not firebase_uids:
        return True

    client = get_firestore_client()
    if client is None:
        return False

    def _delete_many():
        batch = client.batch()
        for firebase_uid in firebase_uids:
            batch.delete(_member_ref(client, group_id, firebase_uid))
        batch.commit()

    await asyncio.to_thread(_delete_many)
    return True


async def get_group_state_document(firebase_uid: str | None, group_id: UUID) -> dict[str, Any] | None:
    """Read a Firestore group-state document if present."""
    if not firebase_uid:
        return None

    client = get_firestore_client()
    if client is None:
        return None

    def _read():
        snapshot = _group_state_ref(client, firebase_uid, group_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    return await asyncio.to_thread(_read)


async def set_group_state_document(
    firebase_uid: str | None,
    group_id: UUID,
    payload: dict[str, Any],
    *,
    merge: bool = True,
) -> bool:
    """Write a group-state document."""
    if not firebase_uid:
        return False

    client = get_firestore_client()
    if client is None:
        return False

    def _write():
        _group_state_ref(client, firebase_uid, group_id).set(payload, merge=merge)

    await asyncio.to_thread(_write)
    return True


async def upsert_group_message(message: GroupMessageSchema) -> bool:
    """Write a message document into Firestore."""
    client = get_firestore_client()
    if client is None:
        return False

    payload = {
        "id": str(message.id),
        "group_id": str(message.group_id),
        "sender_user_id": str(message.sender_user_id),
        "body": message.body,
        "status": message.status,
        "created_at": _isoformat(message.created_at),
        "updated_at": _isoformat(message.updated_at),
        "sender": (
            {
                "id": str(message.sender.id),
                "display_name": message.sender.display_name,
            }
            if message.sender
            else None
        ),
        "attachments": [
            {
                "id": str(attachment.id),
                "message_id": str(attachment.message_id),
                "attachment_kind": attachment.attachment_kind,
                "url": attachment.url,
                "mime_type": attachment.mime_type,
                "file_name": attachment.file_name,
                "size_bytes": attachment.size_bytes,
                "created_at": _isoformat(attachment.created_at),
            }
            for attachment in message.attachments
        ],
        "reply_to_message_id": None,
        "reply_preview": None,
    }

    def _write():
        _message_ref(client, message.group_id, message.id).set(payload, merge=True)

    await asyncio.to_thread(_write)
    return True


async def remove_group_message(message: GroupMessageSchema) -> bool:
    """Mirror a soft-removed message into Firestore."""
    client = get_firestore_client()
    if client is None:
        return False

    payload = {
        "status": message.status,
        "removed_at": _isoformat(message.removed_at),
        "removal_reason": message.removal_reason,
        "updated_at": _isoformat(message.updated_at),
    }

    def _write():
        _message_ref(client, message.group_id, message.id).set(payload, merge=True)

    await asyncio.to_thread(_write)
    return True


async def rebuild_group_membership_state_for_group(
    group_id: UUID,
    member_records: list[tuple[User, GroupMembership]],
    *,
    notifications_enabled: bool = True,
) -> bool:
    """Best-effort helper for manual membership/state reconciliation."""
    client = get_firestore_client()
    if client is None:
        return False

    timestamp = _isoformat(_utcnow())

    def _rebuild():
        batch = client.batch()
        for user, membership in member_records:
            if not user.firebase_uid or membership.status != "active":
                continue
            batch.set(
                _member_ref(client, group_id, user.firebase_uid),
                {
                    "firebase_uid": user.firebase_uid,
                    "user_id": str(user.id),
                    "status": "active",
                    "is_admin": bool(user.is_admin),
                    "joined_at": _isoformat(membership.joined_at or _utcnow()),
                },
                merge=True,
            )
            batch.set(
                _group_state_ref(client, user.firebase_uid, group_id),
                {
                    "unread_count": 0,
                    "notifications_enabled": notifications_enabled,
                    "last_read_message_id": None,
                    "last_activity_at": timestamp,
                },
                merge=True,
            )
        batch.commit()

    await asyncio.to_thread(_rebuild)
    return True
