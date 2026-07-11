from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.crud import voice_logging
from app.db.session import get_db
from app.main import app
from app.models.users import User
from app.schemas.milestone import Milestone
from app.schemas.growth import Growth
from app.schemas.voice import VoiceLogType


def _make_user() -> User:
    user = User(firebase_uid=f"uid_{uuid4().hex}", display_name="Voice User", email="voice@example.com")
    user.id = uuid4()
    return user


class FakeDB:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0
        self.flush_count = 0

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1

    async def refresh(self, _obj):
        self.refresh_count += 1

    async def flush(self):
        self.flush_count += 1


def _override_user(user: User):
    async def _dep():
        return user

    return _dep


def _override_db(fake_db: FakeDB):
    async def _dep():
        yield fake_db

    return _dep


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def _stub_serialize_entry_with_audit(_db, entry, schema_cls, cache=None):
    return schema_cls.model_validate(entry)


def test_analyze_voice_transcript_parses_simple_feeding():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Fed 120 ml at 3 pm",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.should_autosave is True
    assert len(result.actions) == 1
    assert result.actions[0].log_type == VoiceLogType.feeding
    assert result.actions[0].payload["amount_ml"] == 120


def test_analyze_voice_transcript_parses_simple_diaper():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Wet diaper at 8 am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.actions[0].log_type == VoiceLogType.diaper
    assert result.actions[0].payload["diaper_type"] == "wet"


def test_analyze_voice_transcript_expands_counted_diapers_into_separate_actions():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="2 wet diapers and one dirty diaper",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.payload["diaper_type"] for action in result.actions] == ["wet", "wet", "dirty"]


def test_analyze_voice_transcript_parses_single_wet_and_dirty_diaper_as_both():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="one wet and dirty diaper",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.payload["diaper_type"] for action in result.actions] == ["both"]


def test_analyze_voice_transcript_expands_counted_wet_and_dirty_diapers():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="2 wet and dirty diapers",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.payload["diaper_type"] for action in result.actions] == ["both", "both"]


def test_analyze_voice_transcript_expands_diapers_with_shared_timestamp():
    client_now = datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc)
    transcript = "2 wet diapers and a dirty diaper around 3"

    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript=transcript,
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=client_now,
        )
    )

    expected_timestamp = voice_logging._resolve_single_timestamp(
        transcript.lower(),
        "America/Los_Angeles",
        client_now,
    )

    assert result.status == "created"
    assert [action.payload["diaper_type"] for action in result.actions] == ["wet", "wet", "dirty"]
    assert all(action.validated_payload is not None for action in result.actions)
    assert [action.validated_payload.timestamp for action in result.actions] == [
        expected_timestamp,
        expected_timestamp,
        expected_timestamp,
    ]


def test_analyze_voice_transcript_preserves_distinct_timestamps_for_repeated_diapers():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="baby has one wet diaper at 7:30am and second wet diaper at 8:30am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.payload["diaper_type"] for action in result.actions] == ["wet", "wet"]
    assert [action.validated_payload.timestamp.isoformat() for action in result.actions] == [
        "2026-06-07T14:30:00+00:00",
        "2026-06-07T15:30:00+00:00",
    ]


def test_analyze_voice_transcript_splits_repeated_feeding_actions_joined_by_and():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="fed 120 ml at 7:30am and fed 150 ml at 8:30am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.log_type for action in result.actions] == [VoiceLogType.feeding, VoiceLogType.feeding]
    assert [action.payload["amount_ml"] for action in result.actions] == [120, 150]
    assert [action.validated_payload.timestamp.isoformat() for action in result.actions] == [
        "2026-06-07T14:30:00+00:00",
        "2026-06-07T15:30:00+00:00",
    ]


def test_analyze_voice_transcript_splits_mixed_actions_joined_by_plain_and():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="fed 120 ml at 7:30am and wet diaper at 8:30am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.log_type for action in result.actions] == [VoiceLogType.feeding, VoiceLogType.diaper]
    assert [action.validated_payload.timestamp.isoformat() for action in result.actions] == [
        "2026-06-07T14:30:00+00:00",
        "2026-06-07T15:30:00+00:00",
    ]


def test_analyze_voice_transcript_returns_confirmation_for_ambiguous_diapers():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="wet and dirty diapers",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert result.actions == []


def test_analyze_voice_transcript_parses_simple_sleep():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Nap from 1 pm to 3 pm",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 17, 0, tzinfo=timezone.utc),
        )
    )

    assert result.actions[0].log_type == VoiceLogType.sleep
    assert result.actions[0].payload["duration_min"] == 120


def test_analyze_voice_transcript_splits_repeated_sleep_actions_joined_by_and():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="nap from 7:30am to 8:30am and nap from 10am to 11am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.log_type for action in result.actions] == [VoiceLogType.sleep, VoiceLogType.sleep]
    assert [action.payload["duration_min"] for action in result.actions] == [60, 60]
    assert [action.validated_payload.start_time.isoformat() for action in result.actions] == [
        "2026-06-07T14:30:00+00:00",
        "2026-06-07T17:00:00+00:00",
    ]


def test_relative_time_resolution_uses_client_timezone():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Fed 100 ml yesterday morning",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    timestamp = result.actions[0].validated_payload.timestamp
    assert timestamp.isoformat() == "2026-06-06T16:00:00+00:00"


def test_incomplete_mood_payload_needs_confirmation():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Mood happy",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert "energy" in result.actions[0].missing_fields


def test_incomplete_recovery_payload_needs_confirmation():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Recovery update: feeling good",
            baby_id=None,
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert "energy_level" in result.actions[0].missing_fields
    assert "water_intake_oz" in result.actions[0].missing_fields


def test_invalid_growth_payload_needs_confirmation():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Growth update today",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert any(field in result.actions[0].missing_fields for field in ("weight_kg", "height_kg", "head_circumference_cm", "height_cm"))


def test_incomplete_milestone_payload_needs_confirmation(monkeypatch):
    incomplete_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.milestone,
        confidence=0.6,
        payload={"category": "motor"},
    )

    monkeypatch.setattr(voice_logging, "_parse_deterministic_actions", lambda *_args, **_kwargs: [incomplete_action])
    monkeypatch.setattr(voice_logging, "_extract_with_llm", _async_return([]))

    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="milestone update",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert "title" in result.actions[0].missing_fields
    assert "achieved_date" in result.actions[0].missing_fields


def test_missing_baby_id_returns_draft_for_baby_scoped_action():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Fed 100 ml at 2 pm",
            baby_id=None,
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"
    assert "baby_id" in result.actions[0].missing_fields


def test_all_or_nothing_autosave_stays_in_confirmation_when_one_action_is_incomplete():
    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="Fed 120 ml and then mood okay",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"


def test_llm_fallback_high_confidence_autosaves(monkeypatch):
    action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.95,
        payload={
            "feeding_type": "bottle",
            "amount_ml": 120,
            "timestamp": datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        },
    )

    monkeypatch.setattr(voice_logging, "_parse_deterministic_actions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(voice_logging, "_extract_with_llm", _async_return([action]))

    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="use llm",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"


def test_llm_fallback_runs_when_deterministic_parser_under_materializes_recognized_clauses(monkeypatch):
    deterministic_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.95,
        payload={
            "feeding_type": "bottle",
            "amount_ml": 120,
            "timestamp": datetime(2026, 6, 7, 14, 30, tzinfo=timezone.utc),
        },
    )
    llm_actions = [
        voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.feeding,
            confidence=0.95,
            payload={
                "feeding_type": "bottle",
                "amount_ml": 120,
                "timestamp": datetime(2026, 6, 7, 14, 30, tzinfo=timezone.utc),
            },
        ),
        voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.diaper,
            confidence=0.95,
            payload={
                "diaper_type": "wet",
                "timestamp": datetime(2026, 6, 7, 15, 30, tzinfo=timezone.utc),
            },
        ),
    ]

    monkeypatch.setattr(
        voice_logging,
        "_parse_deterministic_actions",
        lambda *_args, **_kwargs: voice_logging.DeterministicParseResult(
            actions=[deterministic_action],
            recognized_clause_count=2,
        ),
    )
    monkeypatch.setattr(voice_logging, "_extract_with_llm", _async_return(llm_actions))

    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="fed 120 ml at 7:30am and wet diaper at 8:30am",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "created"
    assert [action.log_type for action in result.actions] == [VoiceLogType.feeding, VoiceLogType.diaper]


def test_llm_fallback_low_confidence_needs_confirmation(monkeypatch):
    action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.5,
        payload={
            "feeding_type": "bottle",
            "amount_ml": 120,
            "timestamp": datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        },
    )

    monkeypatch.setattr(voice_logging, "_parse_deterministic_actions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(voice_logging, "_extract_with_llm", _async_return([action]))

    result = _run(
        voice_logging.analyze_voice_transcript(
            transcript="use llm",
            baby_id=uuid4(),
            timezone_name="America/Los_Angeles",
            client_now=datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc),
        )
    )

    assert result.status == "needs_confirmation"


def test_create_voice_logs_uses_single_commit(monkeypatch):
    fake_db = FakeDB()
    user_id = uuid4()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_create_feeding_entry(_db, _baby_id, _user_id, _payload, autocommit=True):
        assert autocommit is False
        return SimpleNamespace(id=uuid4(), baby_id=_baby_id, created_by_user_id=_user_id, updated_by_user_id=_user_id, created_at=now, updated_at=now)

    async def fake_create_diaper_entry(_db, _baby_id, _user_id, _payload, autocommit=True):
        assert autocommit is False
        return SimpleNamespace(id=uuid4(), baby_id=_baby_id, created_by_user_id=_user_id, updated_by_user_id=_user_id, created_at=now, updated_at=now)

    monkeypatch.setattr(voice_logging.feeding_entries, "create_feeding_entry", fake_create_feeding_entry)
    monkeypatch.setattr(voice_logging.diaper_entries, "create_diaper_entry", fake_create_diaper_entry)

    feeding_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.95,
        payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now},
        validated_payload=voice_logging.FeedingCreate(feeding_type="bottle", amount_ml=120, duration_min=None, timestamp=now, notes=None),
    )
    diaper_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.diaper,
        confidence=0.95,
        payload={"diaper_type": "wet", "timestamp": now},
        validated_payload=voice_logging.DiaperCreate(diaper_type="wet", timestamp=now, notes=None),
    )

    created = _run(voice_logging.create_voice_logs(fake_db, user_id, baby_id, [feeding_action, diaper_action]))

    assert len(created) == 2
    assert fake_db.commit_count == 1
    assert fake_db.rollback_count == 0
    assert fake_db.refresh_count == 2


def test_create_voice_logs_rolls_back_on_failure(monkeypatch):
    fake_db = FakeDB()
    user_id = uuid4()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_create_feeding_entry(_db, _baby_id, _user_id, _payload, autocommit=True):
        return SimpleNamespace(id=uuid4(), baby_id=_baby_id, created_by_user_id=_user_id, updated_by_user_id=_user_id, created_at=now, updated_at=now)

    async def fake_create_diaper_entry(_db, _baby_id, _user_id, _payload, autocommit=True):
        raise RuntimeError("boom")

    monkeypatch.setattr(voice_logging.feeding_entries, "create_feeding_entry", fake_create_feeding_entry)
    monkeypatch.setattr(voice_logging.diaper_entries, "create_diaper_entry", fake_create_diaper_entry)

    feeding_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.95,
        payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now},
        validated_payload=voice_logging.FeedingCreate(feeding_type="bottle", amount_ml=120, duration_min=None, timestamp=now, notes=None),
    )
    diaper_action = voice_logging.ParsedVoiceAction(
        log_type=VoiceLogType.diaper,
        confidence=0.95,
        payload={"diaper_type": "wet", "timestamp": now},
        validated_payload=voice_logging.DiaperCreate(diaper_type="wet", timestamp=now, notes=None),
    )

    with pytest.raises(RuntimeError):
        _run(voice_logging.create_voice_logs(fake_db, user_id, baby_id, [feeding_action, diaper_action]))

    assert fake_db.commit_count == 0
    assert fake_db.rollback_count == 1


def test_route_autosaves_single_high_confidence_create(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)
    resource = SimpleNamespace(
        id=uuid4(),
        baby_id=baby_id,
        feeding_type="bottle",
        amount_ml=120,
        duration_min=None,
        timestamp=now,
        notes=None,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.feeding,
            confidence=0.95,
            payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now.isoformat()},
            validated_payload=voice_logging.FeedingCreate(feeding_type="bottle", amount_ml=120, duration_min=None, timestamp=now, notes=None),
        )
        return voice_logging.VoiceAnalysisResult(status="created", message="ok", actions=[action])

    async def fake_create_voice_logs(**_kwargs):
        return [voice_logging.CreatedVoiceAction(log_type=VoiceLogType.feeding, confidence=0.95, resource=resource)]

    async def fake_require_baby_edit_permission(_db, requested_baby_id, current_user):
        assert requested_baby_id == baby_id
        assert current_user.id == user.id

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes, "_serialize_entry_with_audit", _stub_serialize_entry_with_audit)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "fed 120 ml",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["created_actions"][0]["log_type"] == "feeding"


def test_route_autosaves_multiple_actions(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_analyze_voice_transcript(**_kwargs):
        actions = [
            voice_logging.ParsedVoiceAction(
                log_type=VoiceLogType.feeding,
                confidence=0.95,
                payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now.isoformat()},
                validated_payload=voice_logging.FeedingCreate(feeding_type="bottle", amount_ml=120, duration_min=None, timestamp=now, notes=None),
            ),
            voice_logging.ParsedVoiceAction(
                log_type=VoiceLogType.diaper,
                confidence=0.95,
                payload={"diaper_type": "wet", "timestamp": now.isoformat()},
                validated_payload=voice_logging.DiaperCreate(diaper_type="wet", timestamp=now, notes=None),
            ),
        ]
        return voice_logging.VoiceAnalysisResult(status="created", message="ok", actions=actions)

    async def fake_create_voice_logs(**_kwargs):
        feeding_resource = SimpleNamespace(
            id=uuid4(),
            baby_id=baby_id,
            feeding_type="bottle",
            amount_ml=120,
            duration_min=None,
            timestamp=now,
            notes=None,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        diaper_resource = SimpleNamespace(
            id=uuid4(),
            baby_id=baby_id,
            diaper_type="wet",
            timestamp=now,
            notes=None,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        return [
            voice_logging.CreatedVoiceAction(log_type=VoiceLogType.feeding, confidence=0.95, resource=feeding_resource),
            voice_logging.CreatedVoiceAction(log_type=VoiceLogType.diaper, confidence=0.95, resource=diaper_resource),
        ]

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes, "_serialize_entry_with_audit", _stub_serialize_entry_with_audit)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "fed 120 ml and then wet diaper",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    assert len(response.json()["created_actions"]) == 2


def test_route_autosaves_growth_even_when_resource_has_datetime_measurement_date(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)
    measurement_dt = datetime(2026, 7, 4, 21, 59, 17, tzinfo=timezone.utc)

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.growth,
            confidence=0.95,
            payload={
                "measurement_date": "2026-07-04",
                "weight_kg": 10.0,
                "height_cm": 70.0,
                "head_circumference_cm": 43.0,
            },
            validated_payload=voice_logging.GrowthCreate(
                measurement_date=measurement_dt.date(),
                weight_kg=10.0,
                height_cm=70.0,
                head_circumference_cm=43.0,
                notes=None,
            ),
        )
        return voice_logging.VoiceAnalysisResult(status="created", message="ok", actions=[action])

    async def fake_create_voice_logs(**_kwargs):
        resource = SimpleNamespace(
            id=uuid4(),
            baby_id=baby_id,
            measurement_date=measurement_dt,
            weight_kg=10.0,
            height_cm=70.0,
            head_circumference_cm=43.0,
            notes=None,
            created_by_user_id=None,
            updated_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
        return [voice_logging.CreatedVoiceAction(log_type=VoiceLogType.growth, confidence=0.95, resource=resource)]

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "weight 10kg 40 percentile height 13 percentile head circumference 8 percentile",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["created_actions"][0]["resource"]["measurement_date"] == "2026-07-04"


def test_route_autosaves_expanded_diaper_actions_in_order(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_create_voice_logs(**kwargs):
        actions = kwargs["actions"]
        assert [action.validated_payload.diaper_type for action in actions] == ["wet", "wet", "dirty"]

        created_actions = []
        for action in actions:
            resource = SimpleNamespace(
                id=uuid4(),
                baby_id=baby_id,
                diaper_type=action.validated_payload.diaper_type,
                timestamp=action.validated_payload.timestamp,
                notes=action.validated_payload.notes,
                created_by_user_id=user.id,
                updated_by_user_id=user.id,
                created_at=now,
                updated_at=now,
            )
            created_actions.append(
                voice_logging.CreatedVoiceAction(
                    log_type=VoiceLogType.diaper,
                    confidence=action.confidence,
                    resource=resource,
                )
            )
        return created_actions

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes, "_serialize_entry_with_audit", _stub_serialize_entry_with_audit)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "2 wet diapers and one dirty diaper",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert [item["resource"]["diaper_type"] for item in payload["created_actions"]] == ["wet", "wet", "dirty"]


def test_route_autosaves_plain_and_compound_actions_in_order(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc)

    async def fake_create_voice_logs(**kwargs):
        actions = kwargs["actions"]
        assert [action.log_type for action in actions] == [VoiceLogType.feeding, VoiceLogType.diaper]
        assert [action.validated_payload.timestamp.isoformat() for action in actions] == [
            "2026-06-07T14:30:00+00:00",
            "2026-06-07T15:30:00+00:00",
        ]

        feeding_resource = SimpleNamespace(
            id=uuid4(),
            baby_id=baby_id,
            feeding_type="bottle",
            amount_ml=actions[0].validated_payload.amount_ml,
            duration_min=actions[0].validated_payload.duration_min,
            timestamp=actions[0].validated_payload.timestamp,
            notes=actions[0].validated_payload.notes,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        diaper_resource = SimpleNamespace(
            id=uuid4(),
            baby_id=baby_id,
            diaper_type=actions[1].validated_payload.diaper_type,
            timestamp=actions[1].validated_payload.timestamp,
            notes=actions[1].validated_payload.notes,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        return [
            voice_logging.CreatedVoiceAction(log_type=VoiceLogType.feeding, confidence=actions[0].confidence, resource=feeding_resource),
            voice_logging.CreatedVoiceAction(log_type=VoiceLogType.diaper, confidence=actions[1].confidence, resource=diaper_resource),
        ]

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes, "_serialize_entry_with_audit", _stub_serialize_entry_with_audit)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "fed 120 ml at 7:30am and wet diaper at 8:30am",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert [item["log_type"] for item in payload["created_actions"]] == ["feeding", "diaper"]


def test_route_returns_needs_confirmation_without_saving(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.mood,
            confidence=0.55,
            payload={"mood": "happy", "timestamp": now.isoformat()},
            missing_fields=["energy"],
        )
        return voice_logging.VoiceAnalysisResult(status="needs_confirmation", message="confirm", actions=[action])

    called = {"create": False}

    async def fake_create_voice_logs(**_kwargs):
        called["create"] = True
        return []

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "mood happy",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_confirmation"
    assert called["create"] is False


def test_route_allows_recovery_without_baby_id(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    now = datetime.now(timezone.utc)
    resource = SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        timestamp=now,
        mood="good",
        energy_level="moderate",
        water_intake_oz=48,
        symptoms=[],
        notes=None,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.recovery,
            confidence=0.95,
            payload={},
            validated_payload=voice_logging.RecoveryEntryCreate(
                timestamp=now,
                mood="good",
                energy_level="moderate",
                water_intake_oz=48,
                symptoms=[],
                notes=None,
            ),
        )
        return voice_logging.VoiceAnalysisResult(status="created", message="ok", actions=[action])

    async def fake_create_voice_logs(**_kwargs):
        return [voice_logging.CreatedVoiceAction(log_type=VoiceLogType.recovery, confidence=0.95, resource=resource)]

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes.voice_logging_crud, "create_voice_logs", fake_create_voice_logs)
    monkeypatch.setattr(routes, "_serialize_entry_with_audit", _stub_serialize_entry_with_audit)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "recovery update",
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "created"


def test_route_baby_log_without_baby_id_returns_confirmation(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    now = datetime.now(timezone.utc)

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.feeding,
            confidence=0.75,
            payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now.isoformat()},
            missing_fields=["baby_id"],
        )
        return voice_logging.VoiceAnalysisResult(status="needs_confirmation", message="confirm", actions=[action])

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "fed 120 ml",
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_confirmation"


def test_route_rejects_unauthorized_baby_access(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_analyze_voice_transcript(**_kwargs):
        action = voice_logging.ParsedVoiceAction(
            log_type=VoiceLogType.feeding,
            confidence=0.95,
            payload={"feeding_type": "bottle", "amount_ml": 120, "timestamp": now.isoformat()},
            validated_payload=voice_logging.FeedingCreate(feeding_type="bottle", amount_ml=120, duration_min=None, timestamp=now, notes=None),
        )
        return voice_logging.VoiceAnalysisResult(status="created", message="ok", actions=[action])

    async def fake_require_baby_edit_permission(_db, _baby_id, _current_user):
        raise HTTPException(status_code=404, detail="Baby not found")

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes.voice_logging_crud, "analyze_voice_transcript", fake_analyze_voice_transcript)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)

    response = client.post(
        "/voice/logs",
        json={
            "transcript": "fed 120 ml",
            "baby_id": str(baby_id),
            "timezone": "America/Los_Angeles",
            "client_now": now.isoformat(),
        },
    )

    assert response.status_code == 404


def test_growth_schema_coerces_datetime_measurement_date():
    now = datetime.now(timezone.utc)

    growth = Growth.model_validate(
        SimpleNamespace(
            id=uuid4(),
            baby_id=uuid4(),
            measurement_date=datetime(2026, 7, 4, 21, 59, 17, tzinfo=timezone.utc),
            weight_kg=10.0,
            height_cm=70.0,
            head_circumference_cm=43.0,
            notes=None,
            created_by_user_id=None,
            updated_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
    )

    assert growth.measurement_date.isoformat() == "2026-07-04"


def test_milestone_schema_coerces_datetime_achieved_date():
    now = datetime.now(timezone.utc)

    milestone = Milestone.model_validate(
        SimpleNamespace(
            id=uuid4(),
            baby_id=uuid4(),
            title="Rolled over",
            category="motor",
            achieved_date=datetime(2026, 7, 4, 21, 59, 17, tzinfo=timezone.utc),
            notes=None,
            photo_url=None,
            created_by_user_id=None,
            updated_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
    )

    assert milestone.achieved_date.isoformat() == "2026-07-04"


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner
