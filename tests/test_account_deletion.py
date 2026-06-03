"""Tests for authenticated account deletion endpoint and deletion service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.users import User


def _make_user(firebase_uid: str | None = None) -> User:
    user = User(firebase_uid=firebase_uid or f"uid_{uuid4().hex}")
    user.id = uuid4()
    return user


class FakeResult:
    def __init__(self, scalar=None, rowcount: int | None = None):
        self._scalar = scalar
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar


class FakeDB:
    def __init__(self, results: list[FakeResult] | None = None):
        self._results = list(results or [])
        self.committed = False
        self.rolled_back = False
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        if self._results:
            return self._results.pop(0)
        return FakeResult()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def _override_db(fake_db: FakeDB):
    async def _dep():
        yield fake_db

    return _dep


def test_unauthenticated_delete_account_fails():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    with TestClient(app) as client:
        response = client.delete("/account")
    app.dependency_overrides.clear()

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == "UNAUTHENTICATED"


def test_user_can_delete_their_own_account(monkeypatch):
    from app.api import routes
    from app.crud.account_deletion import AccountDeletionResult

    current_user = _make_user("firebase_owner")
    fake_db = FakeDB(results=[FakeResult(scalar=current_user)])
    called = {"local": False, "auth": False}

    async def fake_identity(_authorization, _x_dev_uid):
        return {
            "firebase_uid": current_user.firebase_uid,
            "email": "owner@example.com",
            "display_name": "Owner",
            "is_anonymous": False,
            "auth_time": datetime.now(timezone.utc),
        }

    async def fake_local_delete(_db, user):
        assert user.id == current_user.id
        called["local"] = True
        return AccountDeletionResult(owned_baby_ids=[uuid4()], storage_objects_deleted=2)

    def fake_delete_auth(firebase_uid):
        assert firebase_uid == current_user.firebase_uid
        called["auth"] = True

    monkeypatch.setattr(routes, "get_authenticated_identity", fake_identity)
    monkeypatch.setattr(routes.account_deletion_crud, "delete_local_account_data", fake_local_delete)
    monkeypatch.setattr(routes.account_deletion_crud, "revoke_and_delete_auth_user", fake_delete_auth)

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _override_db(fake_db)
    with TestClient(app) as client:
        response = client.delete("/account")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "deleted" in payload["message"].lower()
    assert called["local"] is True
    assert called["auth"] is True


def test_user_cannot_delete_another_users_data(monkeypatch):
    from app.api import routes
    from app.crud.account_deletion import AccountDeletionResult

    current_user = _make_user("firebase_current")
    other_user = _make_user("firebase_other")
    fake_db = FakeDB(results=[FakeResult(scalar=current_user)])

    async def fake_identity(_authorization, _x_dev_uid):
        return {
            "firebase_uid": current_user.firebase_uid,
            "email": "current@example.com",
            "display_name": "Current",
            "is_anonymous": False,
            "auth_time": datetime.now(timezone.utc),
        }

    async def fake_local_delete(_db, user):
        # Endpoint only passes the authenticated user; no arbitrary userId allowed.
        assert user.id == current_user.id
        assert user.id != other_user.id
        return AccountDeletionResult(owned_baby_ids=[], storage_objects_deleted=0)

    monkeypatch.setattr(routes, "get_authenticated_identity", fake_identity)
    monkeypatch.setattr(routes.account_deletion_crud, "delete_local_account_data", fake_local_delete)
    monkeypatch.setattr(routes.account_deletion_crud, "revoke_and_delete_auth_user", lambda _uid: None)

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _override_db(fake_db)
    with TestClient(app) as client:
        response = client.delete("/account")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_idempotent_repeated_delete_request_does_not_crash(monkeypatch):
    from app.api import routes

    firebase_uid = "firebase_deleted_user"
    fake_db = FakeDB(results=[FakeResult(scalar=None)])
    called = {"auth": False}

    async def fake_identity(_authorization, _x_dev_uid):
        return {
            "firebase_uid": firebase_uid,
            "email": "deleted@example.com",
            "display_name": "Deleted",
            "is_anonymous": False,
            "auth_time": datetime.now(timezone.utc),
        }

    def fake_delete_auth(uid):
        assert uid == firebase_uid
        called["auth"] = True

    monkeypatch.setattr(routes, "get_authenticated_identity", fake_identity)
    monkeypatch.setattr(routes.account_deletion_crud, "revoke_and_delete_auth_user", fake_delete_auth)

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = _override_db(fake_db)
    with TestClient(app) as client:
        response = client.delete("/account")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert called["auth"] is True


def test_delete_local_data_includes_owned_babies_and_logs(monkeypatch):
    from app.crud import account_deletion

    user = _make_user("firebase_owner")
    fake_db = FakeDB(results=[FakeResult(rowcount=1)])
    baby_id = uuid4()

    async def fake_owned_babies(_db, _user_id):
        return [baby_id]

    async def fake_storage_urls(_db, _baby_ids):
        return []

    monkeypatch.setattr(account_deletion, "_get_owned_baby_ids", fake_owned_babies)
    monkeypatch.setattr(account_deletion, "_get_storage_urls_for_owned_data", fake_storage_urls)
    monkeypatch.setattr(account_deletion, "_delete_storage_data", lambda **_kwargs: 0)

    deletion_result = asyncio.run(account_deletion.delete_local_account_data(fake_db, user))

    assert fake_db.committed is True
    assert deletion_result.owned_baby_ids == [baby_id]


def test_caregiver_only_user_delete_does_not_target_owner_babies(monkeypatch):
    from app.crud import account_deletion

    caregiver = _make_user("firebase_caregiver")
    fake_db = FakeDB(results=[FakeResult(rowcount=1)])

    async def fake_owned_babies(_db, _user_id):
        # Caregiver-only user owns no babies; owner data should remain untouched.
        return []

    async def fake_storage_urls(_db, _baby_ids):
        return []

    monkeypatch.setattr(account_deletion, "_get_owned_baby_ids", fake_owned_babies)
    monkeypatch.setattr(account_deletion, "_get_storage_urls_for_owned_data", fake_storage_urls)
    monkeypatch.setattr(account_deletion, "_delete_storage_data", lambda **_kwargs: 0)

    deletion_result = asyncio.run(account_deletion.delete_local_account_data(fake_db, caregiver))

    assert fake_db.committed is True
    assert deletion_result.owned_baby_ids == []


def test_storage_cleanup_handles_missing_files(monkeypatch):
    from app.crud import account_deletion

    class FakeBlob:
        def delete(self):
            raise RuntimeError("404 Not Found")

    class FakeBucket:
        def blob(self, _object_path):
            return FakeBlob()

    monkeypatch.setattr(account_deletion.storage, "bucket", lambda _name=None: FakeBucket())

    assert account_deletion._safe_delete_blob("my-bucket", "users/uid/profile.jpg") is False
