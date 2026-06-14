from __future__ import annotations
"""Voice-driven log parsing and orchestration."""

import asyncio
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import diaper_entries, feeding_entries, growth_entries, milestone_entries, mood_entries, recovery_entries, sleep_entries
from app.schemas.diaper import DiaperCreate
from app.schemas.feeding import FeedingCreate
from app.schemas.growth import GrowthCreate
from app.schemas.milestone import MilestoneCreate, MilestoneCategory
from app.schemas.mood import MoodCreate
from app.schemas.recovery import RecoveryEntryCreate
from app.schemas.sleep import SleepCreate
from app.schemas.voice import VoiceLogType

logger = logging.getLogger(__name__)

AUTOSAVE_STATUS = "created"
CONFIRMATION_STATUS = "needs_confirmation"
REJECTED_STATUS = "rejected"

VOICE_CREATE_SCHEMAS: dict[VoiceLogType, type[BaseModel]] = {
    VoiceLogType.feeding: FeedingCreate,
    VoiceLogType.diaper: DiaperCreate,
    VoiceLogType.sleep: SleepCreate,
    VoiceLogType.mood: MoodCreate,
    VoiceLogType.recovery: RecoveryEntryCreate,
    VoiceLogType.growth: GrowthCreate,
    VoiceLogType.milestone: MilestoneCreate,
}

GROWTH_MEASUREMENT_FIELDS = (
    "weight_kg",
    "height_cm",
    "head_circumference_cm",
)

BABY_SCOPED_LOG_TYPES = {
    VoiceLogType.feeding,
    VoiceLogType.diaper,
    VoiceLogType.sleep,
    VoiceLogType.mood,
    VoiceLogType.growth,
    VoiceLogType.milestone,
}

RELATIVE_TIME_DEFAULTS = {
    "morning": time(hour=9, minute=0),
    "afternoon": time(hour=15, minute=0),
    "evening": time(hour=19, minute=0),
    "night": time(hour=21, minute=0),
    "tonight": time(hour=21, minute=0),
}

MOOD_KEYWORDS = {
    "happy": "happy",
    "sad": "sad",
    "anxious": "anxious",
    "okay": "okay",
    "ok": "okay",
    "calm": "calm",
    "fussy": "fussy",
}

ENERGY_KEYWORDS = {
    "high": "high",
    "medium": "medium",
    "low": "low",
}

RECOVERY_MOOD_KEYWORDS = {
    "great": "great",
    "good": "good",
    "okay": "okay",
    "ok": "okay",
    "struggling": "struggling",
    "overwhelmed": "overwhelmed",
}

RECOVERY_ENERGY_KEYWORDS = {
    "very low": "veryLow",
    "low": "low",
    "moderate": "moderate",
    "high": "high",
    "very high": "veryHigh",
}

RECOVERY_SYMPTOMS = {
    "soreness": "soreness",
    "bleeding": "bleeding",
    "cramping": "cramping",
    "breast pain": "breastPain",
    "headache": "headache",
    "nausea": "nausea",
    "anxiety": "anxiety",
    "sadness": "sadness",
    "insomnia": "insomnia",
    "hot flashes": "hotFlashes",
}


@dataclass
class ParsedVoiceAction:
    log_type: VoiceLogType
    confidence: float
    payload: dict[str, Any]
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validated_payload: BaseModel | None = None

    @property
    def requires_baby(self) -> bool:
        return self.log_type in BABY_SCOPED_LOG_TYPES

    @property
    def is_autosave_ready(self) -> bool:
        return (
            self.validated_payload is not None
            and not self.missing_fields
            and self.confidence >= settings.voice_autosave_threshold
        )


@dataclass
class VoiceAnalysisResult:
    status: str
    message: str
    actions: list[ParsedVoiceAction] = field(default_factory=list)

    @property
    def requires_baby_access(self) -> bool:
        return any(action.requires_baby for action in self.actions)

    @property
    def should_autosave(self) -> bool:
        return self.status == AUTOSAVE_STATUS and bool(self.actions)


@dataclass
class CreatedVoiceAction:
    log_type: VoiceLogType
    confidence: float
    resource: Any


class OpenAIVoiceExtractor:
    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def extract(
        self,
        transcript: str,
        timezone_name: str,
        client_now: datetime,
        baby_id: UUID | None,
    ) -> list[ParsedVoiceAction]:
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("OpenAI SDK is not installed; skipping LLM voice extraction")
            return []

        client = OpenAI(api_key=self.api_key)
        prompt = self._build_prompt(transcript, timezone_name, client_now, baby_id)
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract structured Nurture+ log creation actions. "
                            "Return strict JSON with an `actions` array. "
                            "Each action must include `log_type`, `confidence`, "
                            "`payload`, `missing_fields`, and `warnings`."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            logger.warning("OpenAI voice extraction failed: %s", exc)
            return []

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("OpenAI voice extraction returned invalid JSON: %s", exc)
            return []

        actions = parsed.get("actions")
        if not isinstance(actions, list):
            return []

        extracted_actions: list[ParsedVoiceAction] = []
        for raw_action in actions:
            action = _parsed_action_from_llm_payload(raw_action)
            if action:
                extracted_actions.append(action)
        return extracted_actions

    def _build_prompt(
        self,
        transcript: str,
        timezone_name: str,
        client_now: datetime,
        baby_id: UUID | None,
    ) -> str:
        return (
            f"Transcript: {transcript}\n"
            f"Timezone: {timezone_name}\n"
            f"Client now: {client_now.isoformat()}\n"
            f"Selected baby_id: {baby_id}\n"
            "Supported log types: feeding, diaper, sleep, mood, recovery, growth, milestone.\n"
            "Use existing create-schema field names only.\n"
            "For baby-scoped logs, do not include baby_id inside payload.\n"
            "If a required field is missing, leave it out of payload and list it in missing_fields.\n"
            "Confidence must be between 0 and 1.\n"
            "Return JSON only."
        )


def _parsed_action_from_llm_payload(raw_action: Any) -> ParsedVoiceAction | None:
    if not isinstance(raw_action, dict):
        return None
    log_type_value = raw_action.get("log_type")
    payload = raw_action.get("payload")
    confidence = raw_action.get("confidence", 0.0)
    if not isinstance(payload, dict):
        payload = {}
    try:
        log_type = VoiceLogType(log_type_value)
    except Exception:
        return None
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    return ParsedVoiceAction(
        log_type=log_type,
        confidence=max(0.0, min(1.0, confidence_value)),
        payload=payload,
        missing_fields=_string_list(raw_action.get("missing_fields")),
        warnings=_string_list(raw_action.get("warnings")),
    )


async def analyze_voice_transcript(
    transcript: str,
    baby_id: UUID | None,
    timezone_name: str,
    client_now: datetime,
) -> VoiceAnalysisResult:
    normalized = _normalize_transcript(transcript)
    segments = _split_into_segments(normalized)
    deterministic_actions = _parse_deterministic_actions(segments, timezone_name, client_now)
    validated_deterministic = [_validate_action(action, baby_id) for action in deterministic_actions]

    llm_actions: list[ParsedVoiceAction] = []
    if _should_use_llm(normalized, validated_deterministic):
        llm_actions = await _extract_with_llm(transcript, timezone_name, client_now, baby_id)
        llm_actions = [_validate_action(action, baby_id) for action in llm_actions]

    chosen_actions = _choose_actions(validated_deterministic, llm_actions)
    if not chosen_actions:
        return VoiceAnalysisResult(
            status=REJECTED_STATUS,
            message="I couldn’t safely turn that voice note into a log yet.",
        )

    if all(action.is_autosave_ready for action in chosen_actions):
        return VoiceAnalysisResult(
            status=AUTOSAVE_STATUS,
            message="Voice note parsed successfully and ready to save.",
            actions=chosen_actions,
        )

    return VoiceAnalysisResult(
        status=CONFIRMATION_STATUS,
        message="Voice note needs confirmation before saving.",
        actions=chosen_actions,
    )


async def create_voice_logs(
    db: AsyncSession,
    user_id: UUID,
    baby_id: UUID | None,
    actions: list[ParsedVoiceAction],
) -> list[CreatedVoiceAction]:
    if any(action.requires_baby for action in actions) and baby_id is None:
        raise ValueError("baby_id is required for baby-scoped voice logs")

    created_actions: list[CreatedVoiceAction] = []
    created_resources: list[Any] = []
    try:
        for action in actions:
            resource = await _create_single_voice_log(
                db=db,
                user_id=user_id,
                baby_id=baby_id,
                action=action,
            )
            if resource is None:
                raise ValueError(f"Failed to create {action.log_type} voice log")
            created_resources.append(resource)
            created_actions.append(
                CreatedVoiceAction(
                    log_type=action.log_type,
                    confidence=action.confidence,
                    resource=resource,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    for resource in created_resources:
        await db.refresh(resource)
    return created_actions


async def _create_single_voice_log(
    db: AsyncSession,
    user_id: UUID,
    baby_id: UUID | None,
    action: ParsedVoiceAction,
):
    payload_model = action.validated_payload
    if payload_model is None:
        raise ValueError("Cannot create voice log without validated payload")

    if action.log_type == VoiceLogType.feeding:
        return await feeding_entries.create_feeding_entry(db, baby_id, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.diaper:
        return await diaper_entries.create_diaper_entry(db, baby_id, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.sleep:
        return await sleep_entries.create_sleep_entry(db, baby_id, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.mood:
        return await mood_entries.create_mood_entry(db, baby_id, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.recovery:
        return await recovery_entries.create_recovery_entry(db, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.growth:
        return await growth_entries.create_growth_entry(db, baby_id, user_id, payload_model, autocommit=False)
    if action.log_type == VoiceLogType.milestone:
        return await milestone_entries.create_milestone_entry(db, baby_id, user_id, payload_model, autocommit=False)
    raise ValueError(f"Unsupported voice log type: {action.log_type}")


async def _extract_with_llm(
    transcript: str,
    timezone_name: str,
    client_now: datetime,
    baby_id: UUID | None,
) -> list[ParsedVoiceAction]:
    if not settings.openai_api_key:
        return []
    extractor = OpenAIVoiceExtractor(
        api_key=settings.openai_api_key,
        model=settings.voice_llm_model,
    )
    return await extractor.extract(transcript, timezone_name, client_now, baby_id)


def _choose_actions(
    deterministic_actions: list[ParsedVoiceAction],
    llm_actions: list[ParsedVoiceAction],
) -> list[ParsedVoiceAction]:
    if llm_actions:
        if len(llm_actions) > len(deterministic_actions):
            return llm_actions
        if _average_confidence(llm_actions) >= _average_confidence(deterministic_actions):
            return llm_actions
    return deterministic_actions


def _should_use_llm(normalized_transcript: str, actions: list[ParsedVoiceAction]) -> bool:
    if not actions:
        return True
    if any(action.missing_fields for action in actions):
        return True
    if any(action.confidence < settings.voice_autosave_threshold for action in actions):
        return True
    if _indicates_multiple_actions(normalized_transcript) and len(actions) < 2:
        return True
    return False


def _average_confidence(actions: list[ParsedVoiceAction]) -> float:
    if not actions:
        return 0.0
    return sum(action.confidence for action in actions) / len(actions)


def _indicates_multiple_actions(transcript: str) -> bool:
    return any(
        phrase in transcript
        for phrase in (" and then ", " also ", ";", ". ", ", then ", " after that ")
    )


def _normalize_transcript(transcript: str) -> str:
    return re.sub(r"\s+", " ", transcript.strip()).lower()


def _split_into_segments(transcript: str) -> list[str]:
    separators = r"(?:;|\. |\n|, then | and then | after that | also )"
    segments = [segment.strip(" ,.") for segment in re.split(separators, transcript) if segment.strip(" ,.")] 
    return segments or [transcript]


def _parse_deterministic_actions(
    segments: list[str],
    timezone_name: str,
    client_now: datetime,
) -> list[ParsedVoiceAction]:
    actions: list[ParsedVoiceAction] = []
    for segment in segments:
        action = (
            _parse_feeding(segment, timezone_name, client_now)
            or _parse_diaper(segment, timezone_name, client_now)
            or _parse_sleep(segment, timezone_name, client_now)
            or _parse_mood(segment, timezone_name, client_now)
            or _parse_recovery(segment, timezone_name, client_now)
            or _parse_growth(segment, timezone_name, client_now)
            or _parse_milestone(segment, timezone_name, client_now)
        )
        if action:
            actions.append(action)
    return actions


def _parse_feeding(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if not any(keyword in segment for keyword in ("feed", "fed", "bottle", "nursed", "breast")):
        return None
    timestamp = _resolve_single_timestamp(segment, timezone_name, client_now)
    feeding_type = "bottle"
    if "breast left" in segment or "left breast" in segment:
        feeding_type = "breast_left"
    elif "breast right" in segment or "right breast" in segment:
        feeding_type = "breast_right"
    elif "both breasts" in segment or "both sides" in segment:
        feeding_type = "both"

    amount_ml = None
    warnings: list[str] = []
    amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(ml|oz)\b", segment)
    if amount_match:
        amount_value = float(amount_match.group(1))
        unit = amount_match.group(2)
        if unit == "oz":
            amount_ml = int(round(amount_value * 29.5735))
            warnings.append("Converted feeding amount from ounces to milliliters.")
        else:
            amount_ml = int(round(amount_value))

    duration_min = None
    duration_match = re.search(r"for\s+(\d+)\s*(minutes|minute|mins|min|hours|hour|hrs|hr)\b", segment)
    if duration_match:
        duration_min = _duration_to_minutes(int(duration_match.group(1)), duration_match.group(2))

    notes = _extract_notes(segment)
    return ParsedVoiceAction(
        log_type=VoiceLogType.feeding,
        confidence=0.95 if amount_ml is not None or duration_min is not None else 0.88,
        payload={
            "feeding_type": feeding_type,
            "amount_ml": amount_ml,
            "duration_min": duration_min,
            "timestamp": timestamp,
            "notes": notes,
        },
        warnings=warnings,
    )


def _parse_diaper(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if not any(keyword in segment for keyword in ("diaper", "poop", "pooped", "wet", "pee")):
        return None
    timestamp = _resolve_single_timestamp(segment, timezone_name, client_now)
    diaper_type = "wet"
    if any(keyword in segment for keyword in ("dirty", "poop", "pooped")) and any(keyword in segment for keyword in ("wet", "pee")):
        diaper_type = "both"
    elif any(keyword in segment for keyword in ("dirty", "poop", "pooped")):
        diaper_type = "dirty"
    elif "dry diaper" in segment:
        diaper_type = "dry"
    notes = _extract_notes(segment)
    return ParsedVoiceAction(
        log_type=VoiceLogType.diaper,
        confidence=0.96,
        payload={
            "diaper_type": diaper_type,
            "timestamp": timestamp,
            "notes": notes,
        },
    )


def _parse_sleep(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if not any(keyword in segment for keyword in ("sleep", "slept", "nap", "napped", "asleep")):
        return None

    start_time = _resolve_single_timestamp(segment, timezone_name, client_now)
    end_time = None
    duration_min = None

    range_match = re.search(
        r"(?:from|started at)\s+([0-9:apm\s]+)\s+(?:to|until)\s+([0-9:apm\s]+)",
        segment,
    )
    if range_match:
        start_time = _parse_time_expression(range_match.group(1), timezone_name, client_now, segment)
        end_time = _parse_time_expression(range_match.group(2), timezone_name, client_now, segment)
        if start_time and end_time:
            duration_min = int((end_time - start_time).total_seconds() / 60)

    if duration_min is None:
        duration_match = re.search(r"for\s+(\d+)\s*(minutes|minute|mins|min|hours|hour|hrs|hr)\b", segment)
        if duration_match:
            duration_min = _duration_to_minutes(int(duration_match.group(1)), duration_match.group(2))
            if start_time:
                end_time = start_time + timedelta(minutes=duration_min)

    quality = None
    for option in ("great", "good", "fair", "poor"):
        if option in segment:
            quality = option
            break

    return ParsedVoiceAction(
        log_type=VoiceLogType.sleep,
        confidence=0.94 if duration_min is not None or end_time is not None else 0.87,
        payload={
            "start_time": start_time,
            "end_time": end_time,
            "duration_min": duration_min,
            "quality": quality,
            "notes": _extract_notes(segment),
        },
    )


def _parse_mood(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if "mood" not in segment and not any(keyword in segment for keyword in MOOD_KEYWORDS):
        return None
    mood_value = next((value for keyword, value in MOOD_KEYWORDS.items() if keyword in segment), None)
    energy_value = next((value for keyword, value in ENERGY_KEYWORDS.items() if f"energy {keyword}" in segment or f"{keyword} energy" in segment), None)
    payload = {
        "mood": mood_value,
        "energy": energy_value,
        "timestamp": _resolve_single_timestamp(segment, timezone_name, client_now),
        "notes": _extract_notes(segment),
    }
    return ParsedVoiceAction(
        log_type=VoiceLogType.mood,
        confidence=0.9 if mood_value and energy_value else 0.68,
        payload=payload,
    )


def _parse_recovery(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if "recovery" not in segment and "postpartum" not in segment and "water" not in segment and not any(keyword in segment for keyword in RECOVERY_SYMPTOMS):
        return None
    mood_value = next((value for keyword, value in RECOVERY_MOOD_KEYWORDS.items() if keyword in segment), None)
    energy_value = next((value for keyword, value in RECOVERY_ENERGY_KEYWORDS.items() if keyword in segment), None)
    water_match = re.search(r"(\d+)\s*(?:oz|ounces?)\s+of\s+water|water\s+(\d+)\s*(?:oz|ounces?)", segment)
    water_intake = None
    if water_match:
        water_intake = int(next(group for group in water_match.groups() if group is not None))

    symptoms = [value for keyword, value in RECOVERY_SYMPTOMS.items() if keyword in segment]
    return ParsedVoiceAction(
        log_type=VoiceLogType.recovery,
        confidence=0.9 if mood_value and energy_value and water_intake is not None else 0.65,
        payload={
            "timestamp": _resolve_single_timestamp(segment, timezone_name, client_now),
            "mood": mood_value,
            "energy_level": energy_value,
            "water_intake_oz": water_intake,
            "symptoms": symptoms,
            "notes": _extract_notes(segment),
        },
    )


def _parse_growth(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    if not any(keyword in segment for keyword in ("weight", "weighed", "height", "head circumference", "head size", "growth")):
        return None
    measurement_dt = _resolve_single_timestamp(segment, timezone_name, client_now)
    weight_kg = None
    height_cm = None
    head_cm = None
    warnings: list[str] = []

    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilograms|lb|lbs|pounds?)", segment)
    if weight_match:
        value = float(weight_match.group(1))
        unit = weight_match.group(2)
        if unit.startswith("lb") or unit.startswith("pound"):
            weight_kg = round(value * 0.453592, 2)
            warnings.append("Converted weight from pounds to kilograms.")
        else:
            weight_kg = value

    height_match = re.search(r"(\d+(?:\.\d+)?)\s*(cm|centimeters|in|inch|inches)\b", segment)
    if height_match:
        value = float(height_match.group(1))
        unit = height_match.group(2)
        if unit in {"in", "inch", "inches"}:
            height_cm = round(value * 2.54, 2)
            warnings.append("Converted height from inches to centimeters.")
        else:
            height_cm = value

    head_match = re.search(r"head(?: circumference| size)?\s*(?:was|is)?\s*(\d+(?:\.\d+)?)\s*(cm|in|inch|inches)\b", segment)
    if head_match:
        value = float(head_match.group(1))
        unit = head_match.group(2)
        if unit in {"in", "inch", "inches"}:
            head_cm = round(value * 2.54, 2)
            warnings.append("Converted head circumference from inches to centimeters.")
        else:
            head_cm = value

    return ParsedVoiceAction(
        log_type=VoiceLogType.growth,
        confidence=0.9 if any(value is not None for value in (weight_kg, height_cm, head_cm)) else 0.6,
        payload={
            "measurement_date": measurement_dt.date(),
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "head_circumference_cm": head_cm,
            "notes": _extract_notes(segment),
        },
        warnings=warnings,
    )


def _parse_milestone(segment: str, timezone_name: str, client_now: datetime) -> ParsedVoiceAction | None:
    milestone_keywords = ("milestone", "rolled over", "first steps", "smiled", "laughed", "crawled", "sat up")
    if not any(keyword in segment for keyword in milestone_keywords):
        return None

    category = MilestoneCategory.other
    if any(keyword in segment for keyword in ("rolled over", "crawled", "sat up", "first steps")):
        category = MilestoneCategory.motor
    elif any(keyword in segment for keyword in ("smiled", "laughed")):
        category = MilestoneCategory.social
    elif any(keyword in segment for keyword in ("said", "word", "spoke", "language")):
        category = MilestoneCategory.language

    title = _extract_milestone_title(segment)
    achieved_dt = _resolve_single_timestamp(segment, timezone_name, client_now)
    return ParsedVoiceAction(
        log_type=VoiceLogType.milestone,
        confidence=0.88 if title else 0.62,
        payload={
            "title": title,
            "category": category,
            "achieved_date": achieved_dt.date(),
            "notes": _extract_notes(segment),
            "photo_url": None,
        },
    )


def _extract_milestone_title(segment: str) -> str | None:
    cleaned = segment.replace("milestone", "").strip(" .")
    if cleaned:
        return cleaned[:255]
    return None


def _extract_notes(segment: str) -> str | None:
    notes_match = re.search(r"(?:notes?|note)\s*[:\-]\s*(.+)$", segment)
    if notes_match:
        return notes_match.group(1).strip()
    return None


def _resolve_single_timestamp(segment: str, timezone_name: str, client_now: datetime) -> datetime:
    parsed = _parse_time_expression(segment, timezone_name, client_now, segment)
    return parsed or client_now.astimezone(ZoneInfo(timezone_name)).astimezone(timezone.utc)


def _parse_time_expression(
    time_text: str,
    timezone_name: str,
    client_now: datetime,
    full_segment: str,
) -> datetime | None:
    zone = ZoneInfo(timezone_name)
    local_now = client_now.astimezone(zone)
    base_date = local_now.date()

    lowered = time_text.lower()
    if "yesterday" in lowered:
        base_date = base_date - timedelta(days=1)
    elif "tomorrow" in lowered:
        base_date = base_date + timedelta(days=1)

    explicit_date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    if explicit_date_match:
        try:
            base_date = date.fromisoformat(explicit_date_match.group(1))
        except ValueError:
            pass

    for label, default_time in RELATIVE_TIME_DEFAULTS.items():
        if label in lowered:
            return datetime.combine(base_date, default_time, tzinfo=zone).astimezone(timezone.utc)

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lowered)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        return datetime.combine(base_date, time(hour=hour, minute=minute), tzinfo=zone).astimezone(timezone.utc)

    if any(keyword in full_segment for keyword in ("today", "yesterday", "tomorrow")):
        return datetime.combine(base_date, local_now.timetz().replace(tzinfo=None), tzinfo=zone).astimezone(timezone.utc)

    try:
        parsed = date_parser.parse(time_text, fuzzy=True, default=local_now.replace(tzinfo=None))
    except (ValueError, OverflowError, TypeError):
        return None

    localized = parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)
    return localized.astimezone(timezone.utc)


def _duration_to_minutes(value: int, unit: str) -> int:
    return value * 60 if unit.startswith("h") else value


def _validate_action(action: ParsedVoiceAction, baby_id: UUID | None) -> ParsedVoiceAction:
    schema_cls = VOICE_CREATE_SCHEMAS[action.log_type]
    payload = {
        key: value
        for key, value in action.payload.items()
        if value is not None
    }
    missing_fields = list(dict.fromkeys(action.missing_fields))
    warnings = list(dict.fromkeys(action.warnings))

    if action.requires_baby and baby_id is None and "baby_id" not in missing_fields:
        missing_fields.append("baby_id")

    required_fields = {
        name
        for name, field_info in schema_cls.model_fields.items()
        if field_info.is_required()
    }
    for field_name in sorted(required_fields):
        if field_name not in payload:
            missing_fields.append(field_name)

    if action.log_type == VoiceLogType.growth and not any(
        payload.get(field_name) is not None for field_name in GROWTH_MEASUREMENT_FIELDS
    ):
        missing_fields.extend(GROWTH_MEASUREMENT_FIELDS)

    validated_payload = None
    if not missing_fields:
        try:
            validated_payload = schema_cls(**payload)
            payload = validated_payload.model_dump(mode="json")
        except ValidationError as exc:
            missing_fields.extend(_validation_missing_fields(exc))
            warnings.extend(_validation_warning_messages(exc))
    action.payload = payload
    action.missing_fields = list(dict.fromkeys(missing_fields))
    action.warnings = list(dict.fromkeys(warnings))
    action.validated_payload = validated_payload
    return action


def _validation_missing_fields(exc: ValidationError) -> list[str]:
    missing: list[str] = []
    for error in exc.errors():
        if error.get("type") == "missing":
            location = error.get("loc") or []
            if location:
                missing.append(str(location[0]))
    return missing


def _validation_warning_messages(exc: ValidationError) -> list[str]:
    warnings: list[str] = []
    for error in exc.errors():
        if error.get("type") != "missing":
            location = ".".join(str(part) for part in error.get("loc", []))
            message = error.get("msg", "Invalid value")
            warnings.append(f"{location}: {message}" if location else message)
    return warnings


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
