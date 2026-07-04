"""Route-level tests for the additive community groups feature."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.crud.account_deletion import ACCOUNT_DATA_TABLES
from app.db.session import get_db
from app.main import app
from app.models.users import User
from app.schemas.group import (
    Group as GroupSchema,
    GroupMessage as GroupMessageSchema,
    GroupMessageAttachment as GroupMessageAttachmentSchema,
    GroupRequest as GroupRequestSchema,
    GroupState as GroupStateSchema,
    GroupUserSummary,
)


def _make_user(
    *,
    firebase_uid: str | None = None,
    display_name: str | None = None,
    is_admin: bool = False,
    is_anonymous: bool = False,
) -> User:
    user = User(
        firebase_uid=firebase_uid or f"uid_{uuid4().hex}",
        display_name=display_name,
        is_admin=is_admin,
        is_anonymous=is_anonymous,
    )
    user.id = uuid4()
    return user


def _make_group(
    *,
    status: str = "active",
    primary_category: str = "general_parenting",
) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        name="New Moms in Sunnyvale",
        description="A local support group",
        status=status,
        primary_category=primary_category,
        custom_category_label=None,
        locality_label="Sunnyvale",
        city="Sunnyvale",
        state="CA",
        country="USA",
        created_at=now,
        updated_at=now,
    )


def _make_membership(group_id: UUID, user_id: UUID, status: str = "active") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        group_id=group_id,
        user_id=user_id,
        status=status,
        joined_at=now if status == "active" else None,
        left_at=None,
        banned_at=now if status == "banned" else None,
        ban_reason="spam" if status == "banned" else None,
        created_at=now,
        updated_at=now,
    )


def _make_message(group_id: UUID, sender_user_id: UUID, status: str = "active") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        group_id=group_id,
        sender_user_id=sender_user_id,
        body="Welcome everyone",
        status=status,
        removed_at=now if status == "removed" else None,
        removal_reason="spam" if status == "removed" else None,
        created_at=now,
        updated_at=now,
    )


def _make_request(requester_user_id: UUID, status: str = "pending") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        requester_user_id=requester_user_id,
        name="Breastfeeding moms in Sunnyvale",
        description="Support and tips",
        primary_category="breastfeeding",
        custom_category_label=None,
        locality_label="Sunnyvale",
        city="Sunnyvale",
        state="CA",
        country="USA",
        request_note="Would love this group",
        status=status,
        resolution_note=None,
        resolved_group_id=None,
        resolved_by_user_id=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )


class FakeDB:
    async def execute(self, _statement):
        raise AssertionError("Unexpected DB query in this test")


def _override_user(user: User):
    async def _dep():
        return user

    return _dep


def _override_db(fake_db):
    async def _dep():
        yield fake_db

    return _dep


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_group_firestore(monkeypatch):
    from app.api import routes

    async def _true(*_args, **_kwargs):
        return True

    async def _none(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes.group_firestore, "upsert_group_member", _true)
    monkeypatch.setattr(routes.group_firestore, "delete_group_member", _true)
    monkeypatch.setattr(routes.group_firestore, "delete_group_members", _true)
    monkeypatch.setattr(routes.group_firestore, "get_group_state_document", _none)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", _true)
    monkeypatch.setattr(routes.group_firestore, "upsert_group_message", _true)
    monkeypatch.setattr(routes.group_firestore, "remove_group_message", _true)


def test_auth_session_shape_is_unchanged(client):
    user = _make_user(firebase_uid="firebase_123")
    app.dependency_overrides[get_current_user] = _override_user(user)

    response = client.post("/auth/session")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"user_id", "firebase_uid"}
    assert payload["firebase_uid"] == "firebase_123"


def test_anonymous_user_cannot_list_groups(client):
    anonymous_user = _make_user(is_anonymous=True)
    app.dependency_overrides[get_current_user] = _override_user(anonymous_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())

    response = client.get("/groups")

    assert response.status_code == 403
    assert "permanent" in response.json()["detail"].lower()


def test_user_can_discover_groups(client, monkeypatch):
    from app.api import routes

    current_user = _make_user(display_name="Parent")
    group = _make_group()

    async def fake_list_groups(_db, *, tag=None, **_kwargs):
        assert tag == "new moms"
        return [group], 1

    async def fake_serialize_groups(_db, groups, user):
        assert groups == [group]
        assert user.id == current_user.id
        return [
            GroupSchema(
                id=group.id,
                name=group.name,
                description=group.description,
                status="active",
                primary_category=group.primary_category,
                custom_category_label=None,
                locality_label=group.locality_label,
                city=group.city,
                state=group.state,
                country=group.country,
                tags=["new moms"],
                member_count=4,
                membership_status=None,
                can_join=True,
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
        ]

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "list_groups", fake_list_groups)
    monkeypatch.setattr(routes, "_serialize_groups", fake_serialize_groups)

    response = client.get("/groups?tag=New%20Moms")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["can_join"] is True
    assert payload["items"][0]["tags"] == ["new moms"]


def test_non_member_cannot_list_group_members(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()

    async def fake_require(_db, _group_id, _current_user):
        raise HTTPException(status_code=403, detail="Only active group members can access this resource")

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_group_member_or_admin", fake_require)

    response = client.get(f"/groups/{uuid4()}/members")

    assert response.status_code == 403


def test_non_member_cannot_read_group_messages(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()

    async def fake_require(_db, _group_id, _current_user):
        raise HTTPException(status_code=403, detail="Only active group members can access this resource")

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_group_member_or_admin", fake_require)

    response = client.get(f"/groups/{uuid4()}/messages")

    assert response.status_code == 403


def test_user_can_join_active_group(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    membership = _make_membership(uuid4(), current_user.id, status="active")

    async def fake_join_group(_db, group_id, user_id):
        assert group_id == membership.group_id
        assert user_id == current_user.id
        return membership, None

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "join_group", fake_join_group)

    response = client.post(f"/groups/{membership.group_id}/join")

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_banned_user_cannot_join_group(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group_id = uuid4()

    async def fake_join_group(_db, _group_id, _user_id):
        assert _group_id == group_id
        return None, "You are banned from this group"

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "join_group", fake_join_group)

    response = client.post(f"/groups/{group_id}/join")

    assert response.status_code == 403


def test_member_can_read_group_messages(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group_id = uuid4()
    message = _make_message(group_id, current_user.id)

    async def fake_require(_db, requested_group_id, requested_user):
        assert requested_group_id == group_id
        assert requested_user.id == current_user.id
        return None

    async def fake_list_messages(_db, requested_group_id, limit, offset):
        assert requested_group_id == group_id
        assert limit == 50
        assert offset == 0
        return [message], 1

    async def fake_serialize_messages(_db, messages):
        assert messages == [message]
        return [
            GroupMessageSchema(
                id=message.id,
                group_id=group_id,
                sender_user_id=current_user.id,
                body=message.body,
                status="active",
                removed_at=None,
                removal_reason=None,
                created_at=message.created_at,
                updated_at=message.updated_at,
                sender=GroupUserSummary(id=current_user.id, display_name=current_user.display_name),
                attachments=[],
            )
        ]

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_group_member_or_admin", fake_require)
    monkeypatch.setattr(routes.groups_crud, "list_group_messages", fake_list_messages)
    monkeypatch.setattr(routes, "_serialize_group_messages", fake_serialize_messages)

    response = client.get(f"/groups/{group_id}/messages")

    assert response.status_code == 200
    assert response.json()["items"][0]["body"] == "Welcome everyone"


def test_member_can_send_group_message(client, monkeypatch):
    from app.api import routes

    current_user = _make_user(display_name="Parent")
    group = _make_group(status="active")
    membership = _make_membership(group.id, current_user.id, status="active")
    message = _make_message(group.id, current_user.id)

    async def fake_get_group_by_id(_db, group_id):
        assert group_id == group.id
        return group

    async def fake_get_membership(_db, group_id, user_id):
        assert group_id == group.id
        assert user_id == current_user.id
        return membership

    async def fake_create_message(_db, group_id, sender_user_id, body):
        assert group_id == group.id
        assert sender_user_id == current_user.id
        assert body.body == "Hi everyone"
        return message

    async def fake_serialize_messages(_db, messages):
        return [
            GroupMessageSchema(
                id=message.id,
                group_id=group.id,
                sender_user_id=current_user.id,
                body="Hi everyone",
                status="active",
                removed_at=None,
                removal_reason=None,
                created_at=message.created_at,
                updated_at=message.updated_at,
                sender=GroupUserSummary(id=current_user.id, display_name=current_user.display_name),
                attachments=[
                    GroupMessageAttachmentSchema(
                        id=uuid4(),
                        message_id=message.id,
                        attachment_kind="image",
                        url="https://example.com/photo.jpg",
                        mime_type="image/jpeg",
                        file_name="photo.jpg",
                        size_bytes=1234,
                        created_at=message.created_at,
                    )
                ],
            )
        ]

    async def fake_list_active_memberships(*_args, **_kwargs):
        return []

    async def fake_resolve_group_users(*_args, **_kwargs):
        return {}

    async def fake_upsert_message(*_args, **_kwargs):
        return True

    async def fake_set_group_state(*_args, **_kwargs):
        return True

    async def fake_get_group_state(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "get_group_by_id", fake_get_group_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes.groups_crud, "create_group_message", fake_create_message)
    monkeypatch.setattr(routes, "_serialize_group_messages", fake_serialize_messages)
    monkeypatch.setattr(routes.groups_crud, "list_active_group_memberships", fake_list_active_memberships)
    monkeypatch.setattr(routes, "_resolve_group_users", fake_resolve_group_users)
    monkeypatch.setattr(routes.group_firestore, "upsert_group_message", fake_upsert_message)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", fake_set_group_state)
    monkeypatch.setattr(routes.group_firestore, "get_group_state_document", fake_get_group_state)

    response = client.post(
        f"/groups/{group.id}/messages",
        json={
            "body": "Hi everyone",
            "attachments": [
                {
                    "attachment_kind": "image",
                    "url": "https://example.com/photo.jpg",
                    "mime_type": "image/jpeg",
                    "file_name": "photo.jpg",
                    "size_bytes": 1234,
                }
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["attachments"][0]["attachment_kind"] == "image"


def test_user_can_create_group_request(client, monkeypatch):
    from app.api import routes

    current_user = _make_user(display_name="Requester")
    request = _make_request(current_user.id)

    async def fake_create_request(_db, user_id, body):
        assert user_id == current_user.id
        assert body.primary_category == "breastfeeding"
        return request

    async def fake_serialize_requests(_db, requests):
        assert requests == [request]
        return [
            GroupRequestSchema(
                id=request.id,
                requester_user_id=current_user.id,
                name=request.name,
                description=request.description,
                primary_category=request.primary_category,
                custom_category_label=None,
                locality_label=request.locality_label,
                city=request.city,
                state=request.state,
                country=request.country,
                tags=["breastfeeding", "local"],
                request_note=request.request_note,
                status="pending",
                resolution_note=None,
                resolved_group_id=None,
                resolved_at=None,
                created_at=request.created_at,
                updated_at=request.updated_at,
                requester=GroupUserSummary(id=current_user.id, display_name=current_user.display_name),
                resolved_by=None,
            )
        ]

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "create_group_request", fake_create_request)
    monkeypatch.setattr(routes, "_serialize_group_requests", fake_serialize_requests)

    response = client.post(
        "/groups/requests",
        json={
            "name": request.name,
            "description": request.description,
            "primary_category": "breastfeeding",
            "locality_label": "Sunnyvale",
            "city": "Sunnyvale",
            "state": "CA",
            "country": "USA",
            "tags": ["Breastfeeding", "Local"],
            "request_note": request.request_note,
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_admin_can_approve_group_request(client, monkeypatch):
    from app.api import routes

    admin_user = _make_user(display_name="Admin", is_admin=True)
    requester_user = _make_user(display_name="Requester")
    request = _make_request(uuid4(), status="approved")
    request.requester_user_id = requester_user.id
    group = _make_group()
    requester_membership = _make_membership(group.id, requester_user.id, status="active")

    async def fake_approve_request(_db, request_id, resolver_user_id, _body):
        assert request_id == request.id
        assert resolver_user_id == admin_user.id
        return request, group, True, None

    async def fake_serialize_requests(_db, requests):
        return [
            GroupRequestSchema(
                id=request.id,
                requester_user_id=request.requester_user_id,
                name=request.name,
                description=request.description,
                primary_category=request.primary_category,
                custom_category_label=None,
                locality_label=request.locality_label,
                city=request.city,
                state=request.state,
                country=request.country,
                tags=["breastfeeding"],
                request_note=request.request_note,
                status="approved",
                resolution_note=None,
                resolved_group_id=group.id,
                resolved_at=request.created_at,
                created_at=request.created_at,
                updated_at=request.updated_at,
                requester=GroupUserSummary(id=request.requester_user_id, display_name="Requester"),
                resolved_by=GroupUserSummary(id=admin_user.id, display_name=admin_user.display_name),
            )
        ]

    async def fake_serialize_groups(_db, groups, _current_user):
        assert groups == [group]
        return [
            GroupSchema(
                id=group.id,
                name=group.name,
                description=group.description,
                status=group.status,
                primary_category=group.primary_category,
                custom_category_label=None,
                locality_label=group.locality_label,
                city=group.city,
                state=group.state,
                country=group.country,
                tags=["breastfeeding"],
                member_count=1,
                membership_status=None,
                can_join=True,
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
        ]

    async def fake_get_user_by_id(_db, user_id):
        assert user_id == str(requester_user.id)
        return requester_user

    async def fake_get_membership(_db, requested_group_id, user_id):
        assert requested_group_id == group.id
        assert user_id == requester_user.id
        return requester_membership

    async def fake_upsert_member(_user, _membership):
        return True

    async def fake_set_group_state(*_args, **_kwargs):
        return True

    app.dependency_overrides[get_current_user] = _override_user(admin_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "approve_group_request", fake_approve_request)
    monkeypatch.setattr(routes, "_serialize_group_requests", fake_serialize_requests)
    monkeypatch.setattr(routes, "_serialize_groups", fake_serialize_groups)
    monkeypatch.setattr(routes.users_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes.group_firestore, "upsert_group_member", fake_upsert_member)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", fake_set_group_state)

    response = client.post(f"/admin/groups/requests/{request.id}/approve", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["requester_joined"] is True
    assert payload["group"]["id"] == str(group.id)


def test_admin_can_ban_member(client, monkeypatch):
    from app.api import routes

    admin_user = _make_user(is_admin=True)
    member_user = _make_user()
    member_user_id = member_user.id
    membership = _make_membership(uuid4(), member_user_id, status="banned")

    async def fake_ban_member(_db, group_id, user_id, admin_id, ban_reason):
        assert group_id == membership.group_id
        assert user_id == member_user_id
        assert admin_id == admin_user.id
        assert ban_reason == "spam"
        return membership, None

    async def fake_get_user_by_id(_db, user_id):
        assert user_id == str(member_user_id)
        return member_user

    async def fake_delete_group_member(*_args, **_kwargs):
        return True

    async def fake_get_group_state(*_args, **_kwargs):
        return None

    async def fake_set_group_state(*_args, **_kwargs):
        return True

    app.dependency_overrides[get_current_user] = _override_user(admin_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "ban_group_member", fake_ban_member)
    monkeypatch.setattr(routes.users_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(routes.group_firestore, "delete_group_member", fake_delete_group_member)
    monkeypatch.setattr(routes.group_firestore, "get_group_state_document", fake_get_group_state)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", fake_set_group_state)

    response = client.post(
        f"/admin/groups/{membership.group_id}/members/{member_user_id}/ban",
        json={"ban_reason": "spam"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "banned"


def test_admin_can_remove_group_message(client, monkeypatch):
    from app.api import routes

    admin_user = _make_user(display_name="Admin", is_admin=True)
    group_id = uuid4()
    message = _make_message(group_id, uuid4(), status="removed")

    async def fake_remove_message(_db, requested_group_id, message_id, admin_id, removal_reason):
        assert requested_group_id == group_id
        assert message_id == message.id
        assert admin_id == admin_user.id
        assert removal_reason == "spam"
        return message, None

    async def fake_serialize_messages(_db, messages):
        return [
            GroupMessageSchema(
                id=message.id,
                group_id=group_id,
                sender_user_id=message.sender_user_id,
                body=message.body,
                status="removed",
                removed_at=message.removed_at,
                removal_reason="spam",
                created_at=message.created_at,
                updated_at=message.updated_at,
                sender=GroupUserSummary(id=message.sender_user_id, display_name="Member"),
                attachments=[],
            )
        ]

    app.dependency_overrides[get_current_user] = _override_user(admin_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "remove_group_message", fake_remove_message)
    monkeypatch.setattr(routes, "_serialize_group_messages", fake_serialize_messages)

    response = client.delete(
        f"/admin/groups/{group_id}/messages/{message.id}?removal_reason=spam"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "removed"


def test_member_can_get_group_state(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group = _make_group()
    membership = _make_membership(group.id, current_user.id, status="active")
    state = GroupStateSchema(
        group_id=group.id,
        unread_count=3,
        notifications_enabled=True,
        last_read_message_id=uuid4(),
        last_activity_at=datetime.now(timezone.utc),
    )

    async def fake_get_group_by_id(_db, group_id):
        assert group_id == group.id
        return group

    async def fake_get_membership(_db, requested_group_id, user_id):
        assert requested_group_id == group.id
        assert user_id == current_user.id
        return membership

    async def fake_get_or_seed(_db, requested_group_id, user, requested_membership):
        assert requested_group_id == group.id
        assert user.id == current_user.id
        assert requested_membership.id == membership.id
        return state

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "get_group_by_id", fake_get_group_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes, "_get_or_seed_group_state", fake_get_or_seed)

    response = client.get(f"/groups/{group.id}/state")

    assert response.status_code == 200
    assert response.json()["unread_count"] == 3


def test_group_state_self_heals_missing_member_doc(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group = _make_group()
    membership = _make_membership(group.id, current_user.id, status="active")
    captured = {}

    async def fake_get_group_by_id(_db, group_id):
        assert group_id == group.id
        return group

    async def fake_get_membership(_db, requested_group_id, user_id):
        assert requested_group_id == group.id
        assert user_id == current_user.id
        return membership

    async def fake_upsert_member(user, membership_row):
        captured["firebase_uid"] = user.firebase_uid
        captured["membership_id"] = membership_row.id
        return True

    async def fake_get_group_state(_firebase_uid, _group_id):
        return None

    async def fake_latest_message(_db, requested_group_id):
        assert requested_group_id == group.id
        return None

    async def fake_set_group_state(_firebase_uid, requested_group_id, payload, merge=True):
        assert requested_group_id == group.id
        assert merge is True
        return True

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "get_group_by_id", fake_get_group_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes.group_firestore, "upsert_group_member", fake_upsert_member)
    monkeypatch.setattr(routes.group_firestore, "get_group_state_document", fake_get_group_state)
    monkeypatch.setattr(routes.groups_crud, "get_latest_active_group_message", fake_latest_message)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", fake_set_group_state)

    response = client.get(f"/groups/{group.id}/state")

    assert response.status_code == 200
    assert captured["firebase_uid"] == current_user.firebase_uid
    assert captured["membership_id"] == membership.id


def test_member_can_mark_group_state_as_read(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group = _make_group()
    membership = _make_membership(group.id, current_user.id, status="active")
    latest_message = _make_message(group.id, uuid4())
    current_state = GroupStateSchema(
        group_id=group.id,
        unread_count=4,
        notifications_enabled=True,
        last_read_message_id=None,
        last_activity_at=None,
    )
    captured = {}

    async def fake_get_group_by_id(_db, group_id):
        assert group_id == group.id
        return group

    async def fake_get_membership(_db, requested_group_id, user_id):
        assert requested_group_id == group.id
        assert user_id == current_user.id
        return membership

    async def fake_get_or_seed(_db, requested_group_id, user, requested_membership):
        assert requested_group_id == group.id
        assert user.id == current_user.id
        assert requested_membership.id == membership.id
        return current_state

    async def fake_latest_message(_db, requested_group_id):
        assert requested_group_id == group.id
        return latest_message

    async def fake_set_group_state(firebase_uid, requested_group_id, payload, merge=True):
        assert firebase_uid == current_user.firebase_uid
        assert requested_group_id == group.id
        assert merge is True
        captured["payload"] = payload
        return True

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "get_group_by_id", fake_get_group_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes, "_get_or_seed_group_state", fake_get_or_seed)
    monkeypatch.setattr(routes.groups_crud, "get_latest_active_group_message", fake_latest_message)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", fake_set_group_state)

    response = client.put(f"/groups/{group.id}/state", json={"mark_all_read": True})

    assert response.status_code == 200
    assert response.json()["unread_count"] == 0
    assert response.json()["last_read_message_id"] == str(latest_message.id)
    assert captured["payload"]["last_read_message_id"] == str(latest_message.id)


def test_group_state_update_rejects_message_from_other_group(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    group = _make_group()
    membership = _make_membership(group.id, current_user.id, status="active")
    current_state = GroupStateSchema(
        group_id=group.id,
        unread_count=1,
        notifications_enabled=True,
        last_read_message_id=None,
        last_activity_at=None,
    )

    async def fake_get_group_by_id(_db, group_id):
        return group if group_id == group.id else None

    async def fake_get_membership(_db, requested_group_id, user_id):
        assert requested_group_id == group.id
        assert user_id == current_user.id
        return membership

    async def fake_get_or_seed(_db, _group_id, _user, _membership):
        return current_state

    async def fake_get_group_message_by_id(_db, requested_group_id, _message_id):
        assert requested_group_id == group.id
        return None

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "get_group_by_id", fake_get_group_by_id)
    monkeypatch.setattr(routes, "get_group_membership_for_user", fake_get_membership)
    monkeypatch.setattr(routes, "_get_or_seed_group_state", fake_get_or_seed)
    monkeypatch.setattr(routes.groups_crud, "get_group_message_by_id", fake_get_group_message_by_id)

    response = client.put(
        f"/groups/{group.id}/state",
        json={"last_read_message_id": str(uuid4())},
    )

    assert response.status_code == 400


def test_join_group_succeeds_even_if_firestore_sync_fails(client, monkeypatch):
    from app.api import routes

    current_user = _make_user()
    membership = _make_membership(uuid4(), current_user.id, status="active")

    async def fake_join_group(_db, group_id, user_id):
        assert group_id == membership.group_id
        assert user_id == current_user.id
        return membership, None

    async def failing_upsert(*_args, **_kwargs):
        raise RuntimeError("firestore unavailable")

    async def failing_set_state(*_args, **_kwargs):
        raise RuntimeError("firestore unavailable")

    app.dependency_overrides[get_current_user] = _override_user(current_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "join_group", fake_join_group)
    monkeypatch.setattr(routes.group_firestore, "upsert_group_member", failing_upsert)
    monkeypatch.setattr(routes.group_firestore, "set_group_state_document", failing_set_state)

    response = client.post(f"/groups/{membership.group_id}/join")

    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_group_archive_removes_firestore_members_best_effort(client, monkeypatch):
    from app.api import routes

    admin_user = _make_user(is_admin=True)
    group = _make_group(status="archived")
    member_a = _make_user(firebase_uid="member_a")
    member_b = _make_user(firebase_uid="member_b")
    memberships = [
        _make_membership(group.id, member_a.id, status="active"),
        _make_membership(group.id, member_b.id, status="active"),
    ]
    captured = {}

    async def fake_set_group_status(_db, group_id, updated_by_user_id, status_value):
        assert group_id == group.id
        assert updated_by_user_id == admin_user.id
        assert status_value == "archived"
        return group

    async def fake_list_active_memberships(_db, requested_group_id):
        assert requested_group_id == group.id
        return memberships

    async def fake_resolve_users(_db, user_ids):
        assert set(user_ids) == {member_a.id, member_b.id}
        return {member_a.id: member_a, member_b.id: member_b}

    async def fake_delete_members(requested_group_id, firebase_uids):
        assert requested_group_id == group.id
        captured["uids"] = firebase_uids
        return True

    async def fake_get_tags_map(_db, group_ids):
        return {group.id: []}

    async def fake_member_counts(_db, group_ids):
        return {group.id: 2}

    async def fake_memberships_for_user(_db, group_ids, user_id):
        assert user_id == admin_user.id
        return {}

    app.dependency_overrides[get_current_user] = _override_user(admin_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.groups_crud, "set_group_status", fake_set_group_status)
    monkeypatch.setattr(routes.groups_crud, "list_active_group_memberships", fake_list_active_memberships)
    monkeypatch.setattr(routes, "_resolve_group_users", fake_resolve_users)
    monkeypatch.setattr(routes.group_firestore, "delete_group_members", fake_delete_members)
    monkeypatch.setattr(routes.groups_crud, "get_group_tags_map", fake_get_tags_map)
    monkeypatch.setattr(routes.groups_crud, "get_active_member_counts", fake_member_counts)
    monkeypatch.setattr(routes.groups_crud, "get_memberships_for_user", fake_memberships_for_user)

    response = client.post(f"/admin/groups/{group.id}/archive")

    assert response.status_code == 200
    assert captured["uids"] == ["member_a", "member_b"]


def test_group_user_summary_excludes_email():
    summary = GroupUserSummary(id=uuid4(), display_name="Parent")

    assert "email" not in summary.model_dump()


def test_group_tables_are_registered_for_account_deletion():
    assert "group_memberships" in ACCOUNT_DATA_TABLES
    assert "group_messages" in ACCOUNT_DATA_TABLES
    assert "group_requests" in ACCOUNT_DATA_TABLES
