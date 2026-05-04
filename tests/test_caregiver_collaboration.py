"""Route-level tests for caregiver collaboration and audit metadata."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.users import User


def _make_user(
    *,
    firebase_uid: str | None = None,
    display_name: str | None = None,
    email: str | None = None,
    is_anonymous: bool = False,
) -> User:
    user = User(
        firebase_uid=firebase_uid or f"uid_{uuid4().hex}",
        display_name=display_name,
        email=email,
        is_anonymous=is_anonymous,
    )
    user.id = uuid4()
    return user


def _make_baby(user_id: UUID, name: str = "Test Baby"):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        name=name,
        birth_date=date(2024, 1, 1),
        photo_url="https://example.com/baby.jpg",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_access(baby_id: UUID, user_id: UUID, role: str = "owner", status: str = "accepted"):
    return SimpleNamespace(
        id=uuid4(),
        baby_id=baby_id,
        user_id=user_id,
        role=role,
        status=status,
        invited_by_user_id=None,
        invite_email=None,
        invite_token=f"token-{uuid4().hex}",
        invite_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        accepted_at=datetime.now(timezone.utc) if status == "accepted" else None,
        revoked_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_feeding_entry(baby_id: UUID, created_by_user_id: UUID):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        baby_id=baby_id,
        feeding_type="bottle",
        amount_ml=120,
        duration_min=10,
        timestamp=now,
        notes="fed well",
        created_by_user_id=created_by_user_id,
        updated_by_user_id=created_by_user_id,
        created_at=now,
        updated_at=now,
    )


class FakeResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar(self):
        return self._scalar

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, results: list[FakeResult] | None = None):
        self._results = results or []

    async def execute(self, _statement):
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None


def _override_user(user: User):
    async def _dep():
        return user

    return _dep


def _override_db(fake_db: FakeDB):
    async def _dep():
        yield fake_db

    return _dep


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def owner_user() -> User:
    return _make_user(display_name="Owner", email="owner@example.com")


@pytest.fixture
def caregiver_user() -> User:
    return _make_user(display_name="Caregiver", email="caregiver@example.com")


@pytest.fixture
def outsider_user() -> User:
    return _make_user(display_name="Outsider", email="outsider@example.com")


@pytest.fixture
def anonymous_user() -> User:
    return _make_user(is_anonymous=True)


def test_owner_can_invite_caregiver(client, monkeypatch, owner_user):
    from app.api import routes

    baby_id = uuid4()
    invite = _make_access(baby_id, owner_user.id, role="caregiver", status="pending")
    invite.invited_by_user_id = owner_user.id
    invite.invite_email = "dad@example.com"

    async def fake_check_baby_access(_db, requested_baby_id, requested_user_id):
        assert requested_baby_id == baby_id
        assert requested_user_id == owner_user.id
        return _make_access(baby_id, owner_user.id, role="owner")

    async def fake_create_invite(*_args, **_kwargs):
        return invite, None

    app.dependency_overrides[get_current_user] = _override_user(owner_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "check_baby_access", fake_check_baby_access)
    monkeypatch.setattr(routes.baby_access_crud, "create_invite", fake_create_invite)

    response = client.post(
        f"/babies/{baby_id}/caregivers/invite",
        json={"invite_email": "dad@example.com", "role": "caregiver"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["share_code"] == invite.invite_token
    assert payload["invite_email"] == "dad@example.com"


def test_caregiver_cannot_invite_another_caregiver(client, monkeypatch, caregiver_user):
    from app.api import routes

    baby_id = uuid4()

    async def fake_check_baby_access(_db, _baby_id, _user_id):
        return _make_access(baby_id, caregiver_user.id, role="caregiver")

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "check_baby_access", fake_check_baby_access)

    response = client.post(
        f"/babies/{baby_id}/caregivers/invite",
        json={"invite_email": "nanny@example.com", "role": "caregiver"},
    )

    assert response.status_code == 403


def test_invite_token_preview_works(client, monkeypatch, owner_user):
    from app.api import routes

    baby = _make_baby(owner_user.id, name="Mila")
    invite = _make_access(baby.id, owner_user.id, role="caregiver", status="pending")
    invite.invited_by_user_id = owner_user.id
    invite.invite_email = "grandma@example.com"

    async def fake_get_invite_by_token(_db, token):
        assert token == "preview-token"
        invite.invite_token = token
        return invite

    app.dependency_overrides[get_db] = _override_db(
        FakeDB(
            results=[
                FakeResult(scalar=baby),
                FakeResult(scalar=owner_user),
            ]
        )
    )
    monkeypatch.setattr(routes.baby_access_crud, "get_invite_by_token", fake_get_invite_by_token)

    response = client.get("/babies/invites/preview-token")

    assert response.status_code == 200
    payload = response.json()
    assert payload["baby_name"] == "Mila"
    assert payload["is_valid"] is True
    assert payload["status"] == "pending"


def test_valid_invite_can_be_accepted(client, monkeypatch, caregiver_user):
    from app.api import routes

    baby_id = uuid4()
    membership = _make_access(baby_id, caregiver_user.id, role="caregiver", status="accepted")

    async def fake_accept_invite(_db, token, accepting_user_id):
        assert token == "valid-token"
        assert accepting_user_id == caregiver_user.id
        return membership, None

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB(results=[FakeResult(scalar=caregiver_user)]))
    monkeypatch.setattr(routes.baby_access_crud, "accept_invite", fake_accept_invite)

    response = client.post("/babies/invites/accept", json={"token": "valid-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["user"]["id"] == str(caregiver_user.id)


def test_expired_invite_fails(client, monkeypatch, caregiver_user):
    from app.api import routes

    async def fake_accept_invite(_db, token, accepting_user_id):
        assert token == "expired-token"
        assert accepting_user_id == caregiver_user.id
        return None, "This invite has expired"

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.baby_access_crud, "accept_invite", fake_accept_invite)

    response = client.post("/babies/invites/accept", json={"token": "expired-token"})

    assert response.status_code == 410


def test_revoked_invite_fails(client, monkeypatch, caregiver_user):
    from app.api import routes

    async def fake_accept_invite(_db, token, accepting_user_id):
        assert token == "revoked-token"
        assert accepting_user_id == caregiver_user.id
        return None, "This invite has been revoked"

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.baby_access_crud, "accept_invite", fake_accept_invite)

    response = client.post("/babies/invites/accept", json={"token": "revoked-token"})

    assert response.status_code == 410


def test_accepted_caregiver_can_view_baby(client, monkeypatch, caregiver_user, owner_user):
    from app.api import routes

    baby = _make_baby(owner_user.id, name="Noah")

    async def fake_check_baby_access(_db, requested_baby_id, requested_user_id):
        assert requested_baby_id == baby.id
        assert requested_user_id == caregiver_user.id
        return _make_access(baby.id, caregiver_user.id, role="caregiver")

    async def fake_get_caregiver_count(_db, _baby_id):
        return 2

    async def fake_get_owner_summary(_db, _baby_id):
        return owner_user

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB(results=[FakeResult(scalar=baby)]))
    monkeypatch.setattr(routes, "check_baby_access", fake_check_baby_access)
    monkeypatch.setattr(routes.babies_crud, "_get_caregiver_count", fake_get_caregiver_count)
    monkeypatch.setattr(routes.babies_crud, "_get_owner_summary", fake_get_owner_summary)

    response = client.get(f"/babies/{baby.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_user_role"] == "caregiver"
    assert payload["owner"]["id"] == str(owner_user.id)


def test_accepted_caregiver_can_create_entries_for_baby(client, monkeypatch, caregiver_user):
    from app.api import routes

    baby_id = uuid4()
    entry = _make_feeding_entry(baby_id, caregiver_user.id)

    async def fake_require_baby_edit_permission(_db, requested_baby_id, current_user):
        assert requested_baby_id == baby_id
        assert current_user.id == caregiver_user.id
        return _make_access(baby_id, caregiver_user.id, role="caregiver")

    async def fake_create_feeding_entry(_db, requested_baby_id, requested_user_id, _body):
        assert requested_baby_id == baby_id
        assert requested_user_id == caregiver_user.id
        return entry

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB(results=[FakeResult(scalar=caregiver_user), FakeResult(scalar=caregiver_user)]))
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.feeding_crud, "create_feeding_entry", fake_create_feeding_entry)

    response = client.post(
        f"/babies/{baby_id}/feedings",
        json={
            "feeding_type": "bottle",
            "amount_ml": 120,
            "duration_min": 10,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": "fed well",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_by"]["id"] == str(caregiver_user.id)
    assert payload["updated_by"]["id"] == str(caregiver_user.id)


def test_caregiver_cannot_edit_owners_entry(client, monkeypatch, caregiver_user, owner_user):
    from app.api import routes

    baby_id = uuid4()
    entry = _make_feeding_entry(baby_id, owner_user.id)

    async def fake_get_feeding_entry_by_id(_db, _feeding_id, _user_id):
        return entry

    async def fake_get_baby_access_for_user(_db, _baby_id, _user_id):
        return _make_access(baby_id, caregiver_user.id, role="caregiver")

    app.dependency_overrides[get_current_user] = _override_user(caregiver_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.feeding_crud, "get_feeding_entry_by_id", fake_get_feeding_entry_by_id)
    monkeypatch.setattr(routes, "get_baby_access_for_user", fake_get_baby_access_for_user)

    response = client.put(
        f"/feedings/{entry.id}",
        json={"notes": "trying to edit another person's entry"},
    )

    assert response.status_code == 403


def test_owner_can_edit_caregiver_entry(client, monkeypatch, owner_user, caregiver_user):
    from app.api import routes

    baby_id = uuid4()
    entry = _make_feeding_entry(baby_id, caregiver_user.id)
    updated_entry = _make_feeding_entry(baby_id, caregiver_user.id)
    updated_entry.id = entry.id
    updated_entry.notes = "owner updated this"
    updated_entry.updated_by_user_id = owner_user.id

    async def fake_get_feeding_entry_by_id(_db, _feeding_id, _user_id):
        return entry

    async def fake_get_baby_access_for_user(_db, _baby_id, _user_id):
        return _make_access(baby_id, owner_user.id, role="owner")

    async def fake_update_feeding_entry(_db, _feeding_id, requested_user_id, _body, is_owner):
        assert requested_user_id == owner_user.id
        assert is_owner is True
        return updated_entry

    app.dependency_overrides[get_current_user] = _override_user(owner_user)
    app.dependency_overrides[get_db] = _override_db(
        FakeDB(results=[FakeResult(scalar=caregiver_user), FakeResult(scalar=owner_user)])
    )
    monkeypatch.setattr(routes.feeding_crud, "get_feeding_entry_by_id", fake_get_feeding_entry_by_id)
    monkeypatch.setattr(routes, "get_baby_access_for_user", fake_get_baby_access_for_user)
    monkeypatch.setattr(routes.feeding_crud, "update_feeding_entry", fake_update_feeding_entry)

    response = client.put(
        f"/feedings/{entry.id}",
        json={"notes": "owner updated this"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["updated_by"]["id"] == str(owner_user.id)


def test_unauthorized_user_cannot_access_shared_baby(client, monkeypatch, outsider_user):
    from app.api import routes

    async def fake_check_baby_access(_db, _baby_id, _user_id):
        raise HTTPException(status_code=404, detail="Baby not found")

    app.dependency_overrides[get_current_user] = _override_user(outsider_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "check_baby_access", fake_check_baby_access)

    response = client.get(f"/babies/{uuid4()}")

    assert response.status_code == 404


def test_baby_list_returns_owned_and_shared_babies(client, monkeypatch, owner_user):
    from app.api import routes

    owned_baby = _make_baby(owner_user.id, name="Owned Baby")
    shared_baby = _make_baby(uuid4(), name="Shared Baby")
    shared_owner = _make_user(display_name="Other Parent", email="other@example.com")

    async def fake_get_babies_for_user(_db, requested_user_id, limit, offset):
        assert requested_user_id == owner_user.id
        return (
            [
                {"baby": owned_baby, "role": "owner", "caregiver_count": 1, "owner": owner_user},
                {"baby": shared_baby, "role": "caregiver", "caregiver_count": 3, "owner": shared_owner},
            ],
            2,
        )

    async def fake_get_caregiver_count(_db, baby_id):
        return 1 if baby_id == owned_baby.id else 3

    async def fake_get_owner_summary(_db, baby_id):
        return owner_user if baby_id == owned_baby.id else shared_owner

    app.dependency_overrides[get_current_user] = _override_user(owner_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.babies_crud, "get_babies_for_user", fake_get_babies_for_user)
    monkeypatch.setattr(routes.babies_crud, "_get_caregiver_count", fake_get_caregiver_count)
    monkeypatch.setattr(routes.babies_crud, "_get_owner_summary", fake_get_owner_summary)

    response = client.get("/babies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert {item["ownership_type"] for item in payload["items"]} == {"owned", "shared"}


def test_audit_fields_populate_correctly(client, monkeypatch, owner_user):
    from app.api import routes

    baby_id = uuid4()
    entry = _make_feeding_entry(baby_id, owner_user.id)

    async def fake_require_baby_edit_permission(_db, requested_baby_id, current_user):
        assert requested_baby_id == baby_id
        assert current_user.id == owner_user.id
        return _make_access(baby_id, owner_user.id, role="owner")

    async def fake_create_feeding_entry(_db, requested_baby_id, requested_user_id, _body):
        assert requested_user_id == owner_user.id
        return entry

    app.dependency_overrides[get_current_user] = _override_user(owner_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB(results=[FakeResult(scalar=owner_user), FakeResult(scalar=owner_user)]))
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.feeding_crud, "create_feeding_entry", fake_create_feeding_entry)

    response = client.post(
        f"/babies/{baby_id}/feedings",
        json={
            "feeding_type": "bottle",
            "amount_ml": 90,
            "duration_min": 8,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": "audit",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_by_user_id"] == str(owner_user.id)
    assert payload["updated_by_user_id"] == str(owner_user.id)
    assert payload["created_by"]["id"] == str(owner_user.id)
    assert payload["updated_by"]["id"] == str(owner_user.id)


def test_anonymous_user_cannot_accept_invite(client, anonymous_user):
    app.dependency_overrides[get_current_user] = _override_user(anonymous_user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())

    response = client.post("/babies/invites/accept", json={"token": "some-token"})

    assert response.status_code == 403
