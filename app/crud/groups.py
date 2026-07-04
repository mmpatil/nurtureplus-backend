from __future__ import annotations
"""CRUD operations for community groups."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import Group
from app.models.group_membership import GroupMembership
from app.models.group_message import GroupMessage
from app.models.group_message_attachment import GroupMessageAttachment
from app.models.group_request import GroupRequest
from app.models.group_request_tag import GroupRequestTag
from app.models.group_tag import GroupTag
from app.models.users import User
from app.schemas.group import (
    LOCATION_REQUIRED_CATEGORIES,
    GroupCreate,
    GroupMessageCreate,
    GroupRequestApprove,
    GroupRequestCreate,
    GroupRequestMerge,
    GroupRequestReject,
    GroupUpdate,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_search_clause(model, search: str):
    pattern = f"%{search.strip()}%"
    return or_(
        model.name.ilike(pattern),
        model.description.ilike(pattern),
        model.locality_label.ilike(pattern),
        model.city.ilike(pattern),
        model.state.ilike(pattern),
        model.country.ilike(pattern),
    )


def _validate_group_category(
    primary_category: str,
    custom_category_label: str | None,
    locality_label: str | None,
) -> str | None:
    if primary_category == "other" and not custom_category_label:
        return "custom_category_label is required when primary_category is 'other'"
    if primary_category in LOCATION_REQUIRED_CATEGORIES and not locality_label:
        return "locality_label is required for locality-based groups"
    return None


async def _replace_group_tags(
    db: AsyncSession,
    group_id: UUID,
    tags: list[str],
) -> None:
    await db.execute(delete(GroupTag).where(GroupTag.group_id == group_id))
    for tag in tags:
        db.add(GroupTag(group_id=group_id, tag=tag))


async def _replace_group_request_tags(
    db: AsyncSession,
    request_id: UUID,
    tags: list[str],
) -> None:
    await db.execute(delete(GroupRequestTag).where(GroupRequestTag.request_id == request_id))
    for tag in tags:
        db.add(GroupRequestTag(request_id=request_id, tag=tag))


async def _get_group_membership(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> GroupMembership | None:
    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _activate_or_create_membership(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> tuple[bool, GroupMembership]:
    membership = await _get_group_membership(db, group_id, user_id)
    now = _utcnow()

    if membership is None:
        membership = GroupMembership(
            group_id=group_id,
            user_id=user_id,
            status="active",
            joined_at=now,
        )
        db.add(membership)
        return True, membership

    if membership.status == "banned":
        return False, membership

    if membership.status == "active":
        return True, membership

    membership.status = "active"
    membership.joined_at = now
    membership.left_at = None
    membership.banned_at = None
    membership.ban_reason = None
    membership.banned_by_user_id = None
    return True, membership


async def create_group(
    db: AsyncSession,
    created_by_user_id: UUID,
    body: GroupCreate,
) -> Group:
    group = Group(
        name=body.name,
        description=body.description,
        status=body.status,
        primary_category=body.primary_category,
        custom_category_label=body.custom_category_label,
        locality_label=body.locality_label,
        city=body.city,
        state=body.state,
        country=body.country,
        created_by_user_id=created_by_user_id,
        updated_by_user_id=created_by_user_id,
    )
    db.add(group)
    await db.flush()
    await _replace_group_tags(db, group.id, body.tags)
    await db.commit()
    await db.refresh(group)
    return group


async def update_group(
    db: AsyncSession,
    group_id: UUID,
    updated_by_user_id: UUID,
    body: GroupUpdate,
) -> tuple[Group | None, str | None]:
    group = await get_group_by_id(db, group_id)
    if group is None:
        return None, "Group not found"

    payload = body.model_dump(exclude_unset=True)
    tags = payload.pop("tags", None) if "tags" in payload else None

    effective_primary_category = payload.get("primary_category", group.primary_category)
    effective_custom_label = payload.get("custom_category_label", group.custom_category_label)
    effective_locality_label = payload.get("locality_label", group.locality_label)
    error = _validate_group_category(
        effective_primary_category,
        effective_custom_label,
        effective_locality_label,
    )
    if error:
        return None, error

    for field, value in payload.items():
        setattr(group, field, value)
    group.updated_by_user_id = updated_by_user_id

    if "tags" in body.model_dump(exclude_unset=True):
        await _replace_group_tags(db, group.id, tags or [])

    await db.commit()
    await db.refresh(group)
    return group, None


async def set_group_status(
    db: AsyncSession,
    group_id: UUID,
    updated_by_user_id: UUID,
    status_value: str,
) -> Group | None:
    group = await get_group_by_id(db, group_id)
    if group is None:
        return None

    group.status = status_value
    group.updated_by_user_id = updated_by_user_id
    await db.commit()
    await db.refresh(group)
    return group


async def list_groups(
    db: AsyncSession,
    *,
    search: str | None,
    primary_category: str | None,
    tag: str | None,
    city: str | None,
    state: str | None,
    country: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Group], int]:
    query = select(Group).where(Group.status == "active")
    if tag:
        query = query.join(GroupTag, GroupTag.group_id == Group.id).where(GroupTag.tag == tag)
    if primary_category:
        query = query.where(Group.primary_category == primary_category)
    if city:
        query = query.where(Group.city == city)
    if state:
        query = query.where(Group.state == state)
    if country:
        query = query.where(Group.country == country)
    if search:
        query = query.where(_build_search_clause(Group, search))

    query = query.distinct().order_by(Group.name.asc(), Group.created_at.desc())
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def list_admin_groups(
    db: AsyncSession,
    *,
    status_value: str | None,
    search: str | None,
    primary_category: str | None,
    city: str | None,
    state: str | None,
    country: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Group], int]:
    query = select(Group)
    if status_value:
        query = query.where(Group.status == status_value)
    if primary_category:
        query = query.where(Group.primary_category == primary_category)
    if city:
        query = query.where(Group.city == city)
    if state:
        query = query.where(Group.state == state)
    if country:
        query = query.where(Group.country == country)
    if search:
        query = query.where(_build_search_clause(Group, search))

    query = query.order_by(Group.created_at.desc(), Group.name.asc())
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def list_user_groups(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int,
    offset: int,
) -> tuple[list[Group], int]:
    query = (
        select(Group)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(
            GroupMembership.user_id == user_id,
            GroupMembership.status == "active",
        )
        .order_by(Group.updated_at.desc(), Group.name.asc())
    )
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def get_group_by_id(
    db: AsyncSession,
    group_id: UUID,
) -> Group | None:
    result = await db.execute(select(Group).where(Group.id == group_id))
    return result.scalar_one_or_none()


async def get_group_tags_map(
    db: AsyncSession,
    group_ids: list[UUID],
) -> dict[UUID, list[str]]:
    if not group_ids:
        return {}

    result = await db.execute(
        select(GroupTag).where(GroupTag.group_id.in_(group_ids)).order_by(GroupTag.tag.asc())
    )
    tags_by_group: dict[UUID, list[str]] = {group_id: [] for group_id in group_ids}
    for row in result.scalars().all():
        tags_by_group.setdefault(row.group_id, []).append(row.tag)
    return tags_by_group


async def get_active_member_counts(
    db: AsyncSession,
    group_ids: list[UUID],
) -> dict[UUID, int]:
    if not group_ids:
        return {}

    result = await db.execute(
        select(
            GroupMembership.group_id,
            func.count(GroupMembership.id),
        )
        .where(
            GroupMembership.group_id.in_(group_ids),
            GroupMembership.status == "active",
        )
        .group_by(GroupMembership.group_id)
    )
    return {group_id: count for group_id, count in result.all()}


async def get_memberships_for_user(
    db: AsyncSession,
    group_ids: list[UUID],
    user_id: UUID,
) -> dict[UUID, GroupMembership]:
    if not group_ids:
        return {}

    result = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id.in_(group_ids),
            GroupMembership.user_id == user_id,
        )
    )
    return {row.group_id: row for row in result.scalars().all()}


async def list_group_members(
    db: AsyncSession,
    group_id: UUID,
) -> list[GroupMembership]:
    result = await db.execute(
        select(GroupMembership)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "active",
        )
        .order_by(GroupMembership.joined_at.asc(), GroupMembership.created_at.asc())
    )
    return result.scalars().all()


async def list_active_group_memberships(
    db: AsyncSession,
    group_id: UUID,
) -> list[GroupMembership]:
    """Return all active memberships in the group."""
    return await list_group_members(db, group_id)


async def list_banned_members(
    db: AsyncSession,
    group_id: UUID,
) -> list[GroupMembership]:
    result = await db.execute(
        select(GroupMembership)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "banned",
        )
        .order_by(GroupMembership.banned_at.desc(), GroupMembership.created_at.desc())
    )
    return result.scalars().all()


async def join_group(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> tuple[GroupMembership | None, str | None]:
    group = await get_group_by_id(db, group_id)
    if group is None:
        return None, "Group not found"
    if group.status != "active":
        return None, "Only active groups can be joined"

    joined, membership = await _activate_or_create_membership(db, group_id, user_id)
    if not joined:
        return None, "You are banned from this group"

    await db.commit()
    await db.refresh(membership)
    return membership, None


async def leave_group(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> tuple[GroupMembership | None, str | None]:
    membership = await _get_group_membership(db, group_id, user_id)
    if membership is None or membership.status != "active":
        return None, "Active membership not found"

    membership.status = "left"
    membership.left_at = _utcnow()
    await db.commit()
    await db.refresh(membership)
    return membership, None


async def create_group_message(
    db: AsyncSession,
    group_id: UUID,
    sender_user_id: UUID,
    body: GroupMessageCreate,
) -> GroupMessage:
    message = GroupMessage(
        group_id=group_id,
        sender_user_id=sender_user_id,
        body=body.body.strip() if body.body else None,
        status="active",
    )
    db.add(message)
    await db.flush()

    for attachment in body.attachments:
        db.add(
            GroupMessageAttachment(
                message_id=message.id,
                attachment_kind=attachment.attachment_kind,
                url=attachment.url,
                mime_type=attachment.mime_type,
                file_name=attachment.file_name,
                size_bytes=attachment.size_bytes,
            )
        )

    await db.commit()
    await db.refresh(message)
    return message


async def list_group_messages(
    db: AsyncSession,
    group_id: UUID,
    limit: int,
    offset: int,
) -> tuple[list[GroupMessage], int]:
    query = (
        select(GroupMessage)
        .where(
            GroupMessage.group_id == group_id,
            GroupMessage.status == "active",
        )
        .order_by(GroupMessage.created_at.asc(), GroupMessage.id.asc())
    )
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def get_group_message_by_id(
    db: AsyncSession,
    group_id: UUID,
    message_id: UUID,
) -> GroupMessage | None:
    """Return one message in the given group, if present."""
    result = await db.execute(
        select(GroupMessage).where(
            GroupMessage.group_id == group_id,
            GroupMessage.id == message_id,
        )
    )
    return result.scalar_one_or_none()


async def get_latest_active_group_message(
    db: AsyncSession,
    group_id: UUID,
) -> GroupMessage | None:
    """Return the latest active message in a group, if any."""
    result = await db.execute(
        select(GroupMessage)
        .where(
            GroupMessage.group_id == group_id,
            GroupMessage.status == "active",
        )
        .order_by(GroupMessage.created_at.desc(), GroupMessage.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_active_messages_after(
    db: AsyncSession,
    group_id: UUID,
    last_read_message: GroupMessage | None,
) -> int:
    """Count active messages after the provided last-read marker."""
    query = select(func.count()).select_from(GroupMessage).where(
        GroupMessage.group_id == group_id,
        GroupMessage.status == "active",
    )
    if last_read_message is not None:
        query = query.where(
            tuple_(GroupMessage.created_at, GroupMessage.id)
            > tuple_(last_read_message.created_at, last_read_message.id)
        )

    result = await db.execute(query)
    return result.scalar() or 0


async def get_message_attachments_map(
    db: AsyncSession,
    message_ids: list[UUID],
) -> dict[UUID, list[GroupMessageAttachment]]:
    if not message_ids:
        return {}

    result = await db.execute(
        select(GroupMessageAttachment)
        .where(GroupMessageAttachment.message_id.in_(message_ids))
        .order_by(GroupMessageAttachment.created_at.asc(), GroupMessageAttachment.id.asc())
    )
    attachments_by_message: dict[UUID, list[GroupMessageAttachment]] = {
        message_id: [] for message_id in message_ids
    }
    for row in result.scalars().all():
        attachments_by_message.setdefault(row.message_id, []).append(row)
    return attachments_by_message


async def create_group_request(
    db: AsyncSession,
    requester_user_id: UUID,
    body: GroupRequestCreate,
) -> GroupRequest:
    group_request = GroupRequest(
        requester_user_id=requester_user_id,
        name=body.name,
        description=body.description,
        primary_category=body.primary_category,
        custom_category_label=body.custom_category_label,
        locality_label=body.locality_label,
        city=body.city,
        state=body.state,
        country=body.country,
        request_note=body.request_note,
        status="pending",
    )
    db.add(group_request)
    await db.flush()
    await _replace_group_request_tags(db, group_request.id, body.tags)
    await db.commit()
    await db.refresh(group_request)
    return group_request


async def list_group_requests_for_user(
    db: AsyncSession,
    user_id: UUID,
    limit: int,
    offset: int,
) -> tuple[list[GroupRequest], int]:
    query = (
        select(GroupRequest)
        .where(GroupRequest.requester_user_id == user_id)
        .order_by(GroupRequest.created_at.desc(), GroupRequest.id.desc())
    )
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def list_group_requests(
    db: AsyncSession,
    *,
    status_value: str | None,
    search: str | None,
    primary_category: str | None,
    city: str | None,
    state: str | None,
    country: str | None,
    limit: int,
    offset: int,
) -> tuple[list[GroupRequest], int]:
    query = select(GroupRequest)
    if status_value:
        query = query.where(GroupRequest.status == status_value)
    if primary_category:
        query = query.where(GroupRequest.primary_category == primary_category)
    if city:
        query = query.where(GroupRequest.city == city)
    if state:
        query = query.where(GroupRequest.state == state)
    if country:
        query = query.where(GroupRequest.country == country)
    if search:
        query = query.where(_build_search_clause(GroupRequest, search))

    query = query.order_by(GroupRequest.created_at.desc(), GroupRequest.id.desc())
    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    return result.scalars().all(), total


async def get_group_request_tags_map(
    db: AsyncSession,
    request_ids: list[UUID],
) -> dict[UUID, list[str]]:
    if not request_ids:
        return {}

    result = await db.execute(
        select(GroupRequestTag)
        .where(GroupRequestTag.request_id.in_(request_ids))
        .order_by(GroupRequestTag.tag.asc())
    )
    tags_by_request: dict[UUID, list[str]] = {request_id: [] for request_id in request_ids}
    for row in result.scalars().all():
        tags_by_request.setdefault(row.request_id, []).append(row.tag)
    return tags_by_request


async def get_group_request_by_id(
    db: AsyncSession,
    request_id: UUID,
) -> GroupRequest | None:
    result = await db.execute(select(GroupRequest).where(GroupRequest.id == request_id))
    return result.scalar_one_or_none()


async def approve_group_request(
    db: AsyncSession,
    request_id: UUID,
    resolver_user_id: UUID,
    body: GroupRequestApprove,
) -> tuple[GroupRequest | None, Group | None, bool, str | None]:
    group_request = await get_group_request_by_id(db, request_id)
    if group_request is None:
        return None, None, False, "Group request not found"
    if group_request.status != "pending":
        return None, None, False, "Only pending group requests can be approved"

    request_tags = await get_group_request_tags_map(db, [group_request.id])
    tags = body.tags if body.tags is not None else request_tags.get(group_request.id, [])

    name = body.name or group_request.name
    description = body.description if body.description is not None else group_request.description
    primary_category = body.primary_category or group_request.primary_category
    custom_category_label = (
        body.custom_category_label
        if body.custom_category_label is not None
        else group_request.custom_category_label
    )
    locality_label = body.locality_label if body.locality_label is not None else group_request.locality_label
    city = body.city if body.city is not None else group_request.city
    state = body.state if body.state is not None else group_request.state
    country = body.country if body.country is not None else group_request.country

    error = _validate_group_category(primary_category, custom_category_label, locality_label)
    if error:
        return None, None, False, error

    group = Group(
        name=name,
        description=description,
        status="active",
        primary_category=primary_category,
        custom_category_label=custom_category_label,
        locality_label=locality_label,
        city=city,
        state=state,
        country=country,
        created_by_user_id=resolver_user_id,
        updated_by_user_id=resolver_user_id,
    )
    db.add(group)
    await db.flush()
    await _replace_group_tags(db, group.id, tags)

    group_request.status = "approved"
    group_request.resolution_note = body.resolution_note
    group_request.resolved_by_user_id = resolver_user_id
    group_request.resolved_group_id = group.id
    group_request.resolved_at = _utcnow()

    requester_joined, _membership = await _activate_or_create_membership(
        db,
        group.id,
        group_request.requester_user_id,
    )

    await db.commit()
    await db.refresh(group)
    await db.refresh(group_request)
    return group_request, group, requester_joined, None


async def reject_group_request(
    db: AsyncSession,
    request_id: UUID,
    resolver_user_id: UUID,
    body: GroupRequestReject,
) -> tuple[GroupRequest | None, str | None]:
    group_request = await get_group_request_by_id(db, request_id)
    if group_request is None:
        return None, "Group request not found"
    if group_request.status != "pending":
        return None, "Only pending group requests can be rejected"

    group_request.status = "rejected"
    group_request.resolution_note = body.resolution_note
    group_request.resolved_by_user_id = resolver_user_id
    group_request.resolved_group_id = None
    group_request.resolved_at = _utcnow()
    await db.commit()
    await db.refresh(group_request)
    return group_request, None


async def merge_group_request(
    db: AsyncSession,
    request_id: UUID,
    resolver_user_id: UUID,
    body: GroupRequestMerge,
) -> tuple[GroupRequest | None, Group | None, bool, str | None]:
    group_request = await get_group_request_by_id(db, request_id)
    if group_request is None:
        return None, None, False, "Group request not found"
    if group_request.status != "pending":
        return None, None, False, "Only pending group requests can be merged"

    target_group = await get_group_by_id(db, body.target_group_id)
    if target_group is None:
        return None, None, False, "Target group not found"
    if target_group.status != "active":
        return None, None, False, "Target group must be active"

    requester_joined, _membership = await _activate_or_create_membership(
        db,
        target_group.id,
        group_request.requester_user_id,
    )

    group_request.status = "merged"
    group_request.resolution_note = body.resolution_note
    group_request.resolved_by_user_id = resolver_user_id
    group_request.resolved_group_id = target_group.id
    group_request.resolved_at = _utcnow()

    await db.commit()
    await db.refresh(group_request)
    return group_request, target_group, requester_joined, None


async def ban_group_member(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
    admin_user_id: UUID,
    ban_reason: str | None,
) -> tuple[GroupMembership | None, str | None]:
    group = await get_group_by_id(db, group_id)
    if group is None:
        return None, "Group not found"

    user_result = await db.execute(select(User.id).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        return None, "User not found"

    membership = await _get_group_membership(db, group_id, user_id)
    now = _utcnow()

    if membership is None:
        membership = GroupMembership(
            group_id=group_id,
            user_id=user_id,
            status="banned",
            banned_at=now,
            ban_reason=ban_reason,
            banned_by_user_id=admin_user_id,
        )
        db.add(membership)
    else:
        membership.status = "banned"
        membership.banned_at = now
        membership.ban_reason = ban_reason
        membership.banned_by_user_id = admin_user_id
        membership.left_at = membership.left_at or now

    await db.commit()
    await db.refresh(membership)
    return membership, None


async def unban_group_member(
    db: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> tuple[GroupMembership | None, str | None]:
    membership = await _get_group_membership(db, group_id, user_id)
    if membership is None or membership.status != "banned":
        return None, "Banned membership not found"

    membership.status = "left"
    membership.left_at = _utcnow()
    membership.banned_at = None
    membership.ban_reason = None
    membership.banned_by_user_id = None

    await db.commit()
    await db.refresh(membership)
    return membership, None


async def remove_group_message(
    db: AsyncSession,
    group_id: UUID,
    message_id: UUID,
    admin_user_id: UUID,
    removal_reason: str | None,
) -> tuple[GroupMessage | None, str | None]:
    result = await db.execute(
        select(GroupMessage).where(
            GroupMessage.id == message_id,
            GroupMessage.group_id == group_id,
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        return None, "Message not found"

    message.status = "removed"
    message.removed_at = _utcnow()
    message.removed_by_user_id = admin_user_id
    message.removal_reason = removal_reason
    await db.commit()
    await db.refresh(message)
    return message, None
