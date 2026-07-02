from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.crud import food_intelligence
from app.db.session import get_db
from app.main import app
from app.models.baby_food_profile import BabyFoodProfile
from app.models.users import User
from app.schemas.feeding import (
    Feeding,
    FeedingAnalysisDraft,
    FeedingAnalysisRequest,
    FeedingAnalysisResponse,
    FeedingConfirmRequest,
    FeedingCreate,
    FeedingMediaCreate,
    FeedingNutritionEstimateCreate,
    ManualNutritionInput,
    SuggestedFeedingPayload,
)
from app.schemas.food_profile import BabyFoodProfileResponse
from app.schemas.product_analysis import ProductAnalysisResponse, ProductSuitabilityRow


def _make_user() -> User:
    user = User(firebase_uid=f"uid_{uuid4().hex}", display_name="Food User", email="food@example.com")
    user.id = uuid4()
    return user


class FakeDB:
    def __init__(self, results: list[object] | None = None):
        self._results = list(results or [])

    async def execute(self, _statement):
        scalar = self._results.pop(0) if self._results else None
        return SimpleNamespace(scalar_one_or_none=lambda: scalar)

    async def commit(self):
        return None

    async def rollback(self):
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


def test_manual_nutrition_analysis_prefers_manual_values():
    request = FeedingAnalysisRequest(
        feeding=FeedingCreate(
            feeding_type="bottle",
            feeding_category="solid_feed",
            feeding_subtype="meal",
            food_name="apple puree",
            serving_count_offered=1,
            timestamp=datetime.now(timezone.utc),
            notes=None,
            amount_ml=None,
            duration_min=None,
            media=[FeedingMediaCreate(media_role="meal_before", media_url="https://example.com/before.jpg")],
        ),
        manual_nutrition=ManualNutritionInput(
            calories=80,
            protein_g=1,
            carbs_g=20,
            sugar_g=12,
            source="manual",
            servings_offered=1,
            servings_consumed=1,
            raw_payload=None,
        ),
    )

    outcome = food_intelligence._build_feeding_outcome(request)

    assert outcome.confidence == 0.96
    assert outcome.feeding.nutrition_source == "manual"
    assert outcome.nutrition_estimate is not None
    assert outcome.nutrition_estimate.calories == 80


def test_voice_transcript_is_accepted_and_used_for_prefill():
    request = FeedingAnalysisRequest(
        feeding=FeedingCreate(
            feeding_type="bottle",
            feeding_category=None,
            feeding_subtype=None,
            food_name=None,
            serving_count_offered=None,
            serving_count_consumed=None,
            consumed_fraction=None,
            timestamp=datetime.now(timezone.utc),
            notes=None,
            amount_ml=None,
            duration_min=None,
            media=[FeedingMediaCreate(media_role="before_meal_photo", media_url="https://example.com/before.jpg")],
        ),
        voice_transcript="banana puree, about 3 ounces, baby ate most of it",
        autosave=False,
    )

    outcome = food_intelligence._build_feeding_outcome(request)

    assert outcome.feeding.food_name == "Banana Puree"
    assert outcome.feeding.amount_value == 3
    assert outcome.feeding.amount_unit == "oz"
    assert outcome.feeding.consumed_fraction == 0.75
    assert outcome.feeding.media[0].media_role == "meal_before"


def test_explicit_structured_fields_override_voice_transcript():
    request = FeedingAnalysisRequest(
        feeding=FeedingCreate(
            feeding_type="bottle",
            feeding_category="solid_feed",
            feeding_subtype="meal",
            food_name="Apple Puree",
            amount_value=2,
            amount_unit="oz",
            timestamp=datetime.now(timezone.utc),
            notes="keep this note",
            amount_ml=None,
            duration_min=None,
            media=None,
        ),
        voice_transcript="banana puree, about 3 ounces, baby ate most of it",
        autosave=False,
    )

    outcome = food_intelligence._build_feeding_outcome(request)

    assert outcome.feeding.food_name == "Apple Puree"
    assert outcome.feeding.amount_value == 2
    assert outcome.feeding.amount_unit == "oz"
    assert outcome.feeding.notes == "keep this note"


def test_manual_nutrition_wins_over_voice_transcript_and_media():
    request = FeedingAnalysisRequest(
        feeding=FeedingCreate(
            feeding_type="bottle",
            feeding_category="solid_feed",
            feeding_subtype="meal",
            food_name="Banana Puree",
            timestamp=datetime.now(timezone.utc),
            notes=None,
            amount_ml=None,
            duration_min=None,
            media=[FeedingMediaCreate(media_role="before_meal_photo", media_url="https://example.com/before.jpg")],
        ),
        manual_nutrition=ManualNutritionInput(
            calories=90,
            protein_g=2,
            servings_offered=1,
            servings_consumed=1,
        ),
        voice_transcript="baby ate half of it",
        autosave=False,
    )

    outcome = food_intelligence._build_feeding_outcome(request)

    assert outcome.nutrition_estimate is not None
    assert outcome.nutrition_estimate.calories == 90
    assert outcome.feeding.nutrition_source == "manual"


def test_product_assessment_flags_honey_and_allergen_conflicts():
    baby = SimpleNamespace(id=uuid4(), name="Mila", birth_date=date(2025, 12, 1))
    profile = BabyFoodProfile(baby_id=baby.id, allergens=["milk"], avoid_ingredients=["honey"])
    request = SimpleNamespace(
        product_name="Honey Yogurt Bites",
        brand_name="Test Brand",
        ingredients_text="milk, honey, banana",
        nutrition_facts_text="Added Sugars 4g",
        manual_nutrition=None,
    )

    row = food_intelligence._assess_product_for_baby(
        baby,
        profile,
        {
            "added_sugar_g": 4,
            "ingredients": ["milk", "honey", "banana"],
        },
        request,
    )

    assert row.verdict == "bad"
    assert "milk" in row.allergen_hits
    assert "honey" in row.warning_flags


def test_legacy_feeding_create_response_remains_compatible(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    fake_db = FakeDB(results=[user, user])
    baby_id = uuid4()
    now = datetime.now(timezone.utc)
    resource = SimpleNamespace(
        id=uuid4(),
        baby_id=baby_id,
        feeding_type="bottle",
        amount_ml=120,
        duration_min=10,
        timestamp=now,
        notes="fed well",
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    async def fake_create_feeding_entry(*_args, **_kwargs):
        return resource

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.feeding_crud, "create_feeding_entry", fake_create_feeding_entry)

    response = client.post(
        f"/babies/{baby_id}/feedings",
        json={
            "feeding_type": "bottle",
            "amount_ml": 120,
            "duration_min": 10,
            "timestamp": now.isoformat(),
            "notes": "fed well",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feeding_type"] == "bottle"
    assert payload["amount_ml"] == 120
    assert payload["notes"] == "fed well"
    assert payload["media"] == []
    assert payload["nutrition_estimate"] is None


def test_feeding_options_route_returns_age_based_choices(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    baby_id = uuid4()

    async def fake_check_baby_access(*_args, **_kwargs):
        return None

    async def fake_get_options(*_args, **_kwargs):
        return SimpleNamespace(
            age_months=8,
            age_band="6-11 months",
            options=[
                {"category": "milk_feed", "subtype": "bottle_formula", "label": "Bottle of formula"},
                {"category": "solid_feed", "subtype": "puree", "label": "Puree"},
            ],
        )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "check_baby_access", fake_check_baby_access)
    monkeypatch.setattr(routes.feeding_crud, "get_feeding_options_for_baby", fake_get_options)

    response = client.get(f"/babies/{baby_id}/feeding-options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["age_band"] == "6-11 months"
    assert any(option["subtype"] == "puree" for option in payload["options"])


def test_analyze_feeding_route_returns_draft_without_saving(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    async def fake_analyze_feeding(*_args, **_kwargs):
        feeding = FeedingCreate(
            feeding_type="bottle",
            feeding_category="solid_feed",
            feeding_subtype="meal",
            food_name="oatmeal",
            amount_ml=None,
            duration_min=None,
            timestamp=now,
            notes=None,
            media=[FeedingMediaCreate(media_role="meal_before", media_url="https://example.com/before.jpg")],
        )
        return FeedingAnalysisResponse(
            status="needs_confirmation",
            message="Review required",
            confidence=0.72,
            warnings=["Review amount"],
            draft=FeedingAnalysisDraft(
                feeding=feeding,
                nutrition_estimate=FeedingNutritionEstimateCreate(calories=55, source="photo_estimate"),
                confidence=0.72,
                warnings=["Nutrition was estimated from meal context and may need review."],
            ),
            suggested_feeding=SuggestedFeedingPayload(
                **feeding.model_dump(exclude={"nutrition_estimate"}),
                nutrition_estimate=FeedingNutritionEstimateCreate(calories=55, source="photo_estimate"),
            ),
        )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.food_intelligence_crud, "analyze_feeding", fake_analyze_feeding)

    response = client.post(
        f"/babies/{baby_id}/feedings/analyze",
        json={
            "feeding": {
                "feeding_type": "bottle",
                "feeding_category": "solid_feed",
                "feeding_subtype": "meal",
                "food_name": "oatmeal",
                "timestamp": now.isoformat(),
                "media": [
                    {"media_role": "meal_before", "media_url": "https://example.com/before.jpg"}
                ],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_confirmation"
    assert payload["suggested_feeding"]["food_name"] == "oatmeal"
    assert payload["warnings"] == ["Review amount"]


def test_analyze_feeding_route_accepts_voice_transcript_only(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    async def fake_analyze_feeding(*_args, **_kwargs):
        suggested = SuggestedFeedingPayload(
            feeding_type="bottle",
            feeding_category="solid_feed",
            feeding_subtype="meal",
            food_name="Banana Puree",
            brand_name="Homemade",
            amount_value=3,
            amount_unit="oz",
            serving_count_offered=1,
            serving_count_consumed=0.75,
            consumed_fraction=0.75,
            analysis_status="needs_confirmation",
            analysis_confidence=0.82,
            nutrition_source="estimated",
            amount_ml=None,
            duration_min=None,
            timestamp=now,
            notes="banana puree, about 3 ounces, baby ate most of it",
            media=[],
            nutrition_estimate=FeedingNutritionEstimateCreate(calories=70, protein_g=1, iron_mg=0.4, calcium_mg=8),
        )
        return FeedingAnalysisResponse(
            status="needs_confirmation",
            message="Prefilled what I could from the provided meal details.",
            confidence=0.82,
            warnings=["Please double-check the amount."],
            draft=FeedingAnalysisDraft(
                feeding=FeedingCreate(**suggested.model_dump(exclude={"nutrition_estimate"})),
                nutrition_estimate=suggested.nutrition_estimate,
                confidence=0.82,
                warnings=["Please double-check the amount."],
            ),
            suggested_feeding=suggested,
        )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.food_intelligence_crud, "analyze_feeding", fake_analyze_feeding)

    response = client.post(
        f"/babies/{baby_id}/feedings/analyze",
        json={
            "feeding": {
                "feeding_type": "bottle",
                "timestamp": now.isoformat(),
            },
            "voice_transcript": "banana puree, about 3 ounces, baby ate most of it",
            "autosave": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_confirmation"
    assert payload["suggested_feeding"]["food_name"] == "Banana Puree"
    assert payload["draft"]["feeding"]["notes"] == "banana puree, about 3 ounces, baby ate most of it"


def test_autosave_false_rejected_when_no_usable_suggestion():
    request = FeedingAnalysisRequest(
        feeding=FeedingCreate(
            feeding_type="bottle",
            timestamp=datetime.now(timezone.utc),
            amount_ml=None,
            duration_min=None,
            notes=None,
            media=None,
        ),
        voice_transcript="",
        autosave=False,
    )

    outcome = asyncio.run(
        food_intelligence.analyze_feeding(
            FakeDB(),
            uuid4(),
            uuid4(),
            request,
        )
    )

    assert outcome.status == "rejected"
    assert outcome.suggested_feeding is None


def test_autosave_false_never_writes(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    baby_id = uuid4()
    fake_db = FakeDB()
    state = {"create_called": False}

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    async def fake_create_feeding_entry(*_args, **_kwargs):
        state["create_called"] = True
        return None

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(fake_db)
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(food_intelligence.feeding_entries, "create_feeding_entry", fake_create_feeding_entry)

    response = client.post(
        f"/babies/{baby_id}/feedings/analyze",
        json={
            "feeding": {
                "feeding_type": "bottle",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "media": [{"media_role": "before_meal_photo", "media_url": "https://example.com/photo.jpg"}],
            },
            "voice_transcript": "banana puree",
            "autosave": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_confirmation"
    assert state["create_called"] is False


def test_confirm_feeding_analysis_route_saves_reviewed_draft(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    baby_id = uuid4()
    now = datetime.now(timezone.utc)

    async def fake_require_baby_edit_permission(*_args, **_kwargs):
        return None

    async def fake_confirm(*_args, **_kwargs):
        return Feeding.model_validate(
            {
                "id": str(uuid4()),
                "baby_id": str(baby_id),
                "feeding_type": "bottle",
                "feeding_category": "solid_feed",
                "feeding_subtype": "meal",
                "food_name": "banana mash",
                "timestamp": now.isoformat(),
                "amount_ml": None,
                "duration_min": None,
                "notes": None,
                "created_by_user_id": str(user.id),
                "updated_by_user_id": str(user.id),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "media": [],
                "nutrition_estimate": None,
            }
        )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes, "require_baby_edit_permission", fake_require_baby_edit_permission)
    monkeypatch.setattr(routes.food_intelligence_crud, "confirm_feeding_analysis", fake_confirm)

    response = client.post(
        f"/babies/{baby_id}/feedings/confirm",
        json={
            "feeding": {
                "feeding_type": "bottle",
                "feeding_category": "solid_feed",
                "feeding_subtype": "meal",
                "food_name": "banana mash",
                "timestamp": now.isoformat(),
            }
        },
    )

    assert response.status_code == 201
    assert response.json()["food_name"] == "banana mash"


def test_product_analysis_route_returns_multi_child_matrix(client, monkeypatch):
    from app.api import routes

    user = _make_user()
    now = datetime.now(timezone.utc)

    async def fake_analyze_product(*_args, **_kwargs):
        return ProductAnalysisResponse(
            id=uuid4(),
            product_name="Toddler Snack",
            brand_name="Brand",
            status="completed",
            confidence=0.91,
            parsed_facts={"added_sugar_g": 4},
            package_front_url="https://example.com/front.jpg",
            package_back_url="https://example.com/back.jpg",
            ingredients_text="banana, milk",
            nutrition_facts_text="Added Sugars 4g",
            suitability=[
                ProductSuitabilityRow(
                    baby_id=uuid4(),
                    baby_name="Ava",
                    life_stage="6-11 months",
                    verdict="bad",
                    confidence=0.91,
                    reasons=["Added sugar is not ideal for babies under 12 months."],
                    warning_flags=["added_sugar"],
                    allergen_hits=[],
                ),
                ProductSuitabilityRow(
                    baby_id=uuid4(),
                    baby_name="Leo",
                    life_stage="12-35 months",
                    verdict="okay",
                    confidence=0.91,
                    reasons=["Moderate added sugar."],
                    warning_flags=["added_sugar"],
                    allergen_hits=[],
                ),
            ],
            created_at=now,
            updated_at=now,
        )

    app.dependency_overrides[get_current_user] = _override_user(user)
    app.dependency_overrides[get_db] = _override_db(FakeDB())
    monkeypatch.setattr(routes.food_intelligence_crud, "analyze_product", fake_analyze_product)

    response = client.post(
        "/food-products/analyze",
        json={
            "product_name": "Toddler Snack",
            "ingredients_text": "banana, milk",
            "nutrition_facts_text": "Added Sugars 4g",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["suitability"]) == 2
    assert {row["verdict"] for row in payload["suitability"]} == {"bad", "okay"}


def test_account_deletion_collects_product_analysis_urls(monkeypatch):
    from app.crud import account_deletion

    user = _make_user()
    captured: dict[str, list[str]] = {}

    class DeleteResult:
        rowcount = 1

    class DeleteDB:
        async def execute(self, _statement):
            return DeleteResult()

        async def commit(self):
            return None

        async def rollback(self):
            return None

    async def fake_owned_babies(_db, _user_id):
        return []

    async def fake_storage_urls(_db, _baby_ids):
        return ["gs://bucket/babies/abc/meal-before.jpg"]

    async def fake_user_analysis_urls(_db, _user_id):
        return ["gs://bucket/users/uid/package-front.jpg"]

    def fake_delete_storage_data(**kwargs):
        captured["storage_urls"] = list(kwargs["storage_urls"])
        return 0

    monkeypatch.setattr(account_deletion, "_get_owned_baby_ids", fake_owned_babies)
    monkeypatch.setattr(account_deletion, "_get_storage_urls_for_owned_data", fake_storage_urls)
    monkeypatch.setattr(account_deletion, "_get_storage_urls_for_user_analyses", fake_user_analysis_urls)
    monkeypatch.setattr(account_deletion, "_delete_storage_data", fake_delete_storage_data)

    asyncio.run(account_deletion.delete_local_account_data(DeleteDB(), user))

    assert captured["storage_urls"] == [
        "gs://bucket/babies/abc/meal-before.jpg",
        "gs://bucket/users/uid/package-front.jpg",
    ]
