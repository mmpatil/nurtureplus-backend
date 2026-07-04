# Nurture+ Community Groups API Reference

This document is a frontend-ready reference for the Groups MVP.

All Groups endpoints are additive and backward compatible with the existing API.

## Base URL

```text
Development: http://localhost:8000
Production:  https://api.nurture-app.com
```

## Authentication

All Groups endpoints require an authenticated user.

Use Firebase ID token in production:

```http
Authorization: Bearer <firebase_id_token>
```

For local development with `DEV_BYPASS_AUTH=true`:

```http
X-Dev-Uid: <test-user-id>
```

## Access Rules

- Anonymous users cannot use any Groups endpoint.
- All `/groups/*` endpoints require a permanent authenticated account.
- All `/admin/groups/*` endpoints require `users.is_admin = true`.
- Only active group members or admins can read member lists and messages.
- Only active group members can send messages.
- Banned users cannot rejoin a group.

## Common Status Codes

- `200` Success
- `201` Created
- `204` No Content
- `400` Bad Request
- `401` Unauthorized
- `403` Forbidden
- `404` Not Found
- `409` Conflict
- `422` Validation Error

## Error Shape

Standard API errors use:

```json
{
  "detail": "Human-readable error message"
}
```

FastAPI validation errors use:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Validation error message",
      "type": "validation_error_type"
    }
  ]
}
```

## Enums

### GroupPrimaryCategory

```text
locality
residential_community
workplace
breastfeeding
new_mothers
baby_age
toddler_mothers
pregnancy
postpartum_support
general_parenting
other
```

### GroupStatus

```text
active
archived
```

### GroupMembershipStatus

```text
active
left
banned
```

### GroupMessageStatus

```text
active
removed
```

### GroupRequestStatus

```text
pending
approved
rejected
merged
```

### AttachmentKind

```text
image
video
audio
file
link
```

## Validation Rules

- `locality_label` is required when `primary_category` is `locality`, `residential_community`, or `workplace`.
- `custom_category_label` is required when `primary_category` is `other`.
- `name` max length: `120`
- `description` max length: `2000`
- `request_note` max length: `2000`
- `message.body` max length: `4000`
- `ban_reason` max length: `1000`
- `tags` are normalized to lowercase, trimmed, and deduplicated.
- A message must contain either non-empty `body` or at least one attachment.

## TypeScript Contracts

```ts
export type GroupPrimaryCategory =
  | "locality"
  | "residential_community"
  | "workplace"
  | "breastfeeding"
  | "new_mothers"
  | "baby_age"
  | "toddler_mothers"
  | "pregnancy"
  | "postpartum_support"
  | "general_parenting"
  | "other";

export type GroupStatus = "active" | "archived";
export type GroupMembershipStatus = "active" | "left" | "banned";
export type GroupMessageStatus = "active" | "removed";
export type GroupRequestStatus = "pending" | "approved" | "rejected" | "merged";
export type AttachmentKind = "image" | "video" | "audio" | "file" | "link";

export interface GroupUserSummary {
  id: string;
  display_name: string | null;
}

export interface Group {
  id: string;
  name: string;
  description: string | null;
  primary_category: GroupPrimaryCategory;
  custom_category_label: string | null;
  locality_label: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  tags: string[];
  status: GroupStatus;
  member_count: number;
  membership_status: GroupMembershipStatus | null;
  can_join: boolean;
  created_at: string;
  updated_at: string;
}

export interface GroupListResponse {
  items: Group[];
  total: number;
  limit: number;
  offset: number;
}

export interface GroupMembershipResponse {
  id: string;
  group_id: string;
  user_id: string;
  status: GroupMembershipStatus;
  joined_at: string | null;
  left_at: string | null;
  banned_at: string | null;
  ban_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  status: GroupMembershipStatus;
  joined_at: string | null;
  created_at: string;
  updated_at: string;
  user: GroupUserSummary | null;
}

export interface GroupMemberListResponse {
  items: GroupMember[];
  total: number;
}

export interface GroupMessageAttachment {
  id: string;
  message_id: string;
  attachment_kind: AttachmentKind;
  url: string;
  mime_type: string | null;
  file_name: string | null;
  size_bytes: number | null;
  created_at: string;
}

export interface GroupMessage {
  id: string;
  group_id: string;
  sender_user_id: string;
  body: string | null;
  status: GroupMessageStatus;
  removed_at: string | null;
  removal_reason: string | null;
  created_at: string;
  updated_at: string;
  sender: GroupUserSummary | null;
  attachments: GroupMessageAttachment[];
}

export interface GroupMessageListResponse {
  items: GroupMessage[];
  total: number;
  limit: number;
  offset: number;
}

export interface GroupState {
  group_id: string;
  unread_count: number;
  notifications_enabled: boolean;
  last_read_message_id: string | null;
  last_activity_at: string | null;
}

export interface GroupRequest {
  id: string;
  requester_user_id: string;
  name: string;
  description: string | null;
  primary_category: GroupPrimaryCategory;
  custom_category_label: string | null;
  locality_label: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  tags: string[];
  request_note: string | null;
  status: GroupRequestStatus;
  resolution_note: string | null;
  resolved_group_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  requester: GroupUserSummary | null;
  resolved_by: GroupUserSummary | null;
}

export interface GroupRequestListResponse {
  items: GroupRequest[];
  total: number;
  limit: number;
  offset: number;
}

export interface GroupRequestResolutionResponse {
  request: GroupRequest;
  group: Group | null;
  requester_joined: boolean;
}
```

## User Endpoints

### 1. List Discoverable Groups

```http
GET /groups
```

Query params:

- `search?: string`
- `primary_category?: GroupPrimaryCategory`
- `tag?: string`
- `city?: string`
- `state?: string`
- `country?: string`
- `limit?: number` default `20`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupListResponse`

Notes:

- Returns active groups only.
- `tag` matching is normalized to lowercase/trimmed server-side.

### 2. List My Joined Groups

```http
GET /groups/mine
```

Query params:

- `limit?: number` default `20`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupListResponse`

Notes:

- Returns groups where current user has active membership.

### 3. Create Group Request

```http
POST /groups/requests
Content-Type: application/json
```

Request body:

```json
{
  "name": "Moms in South Mumbai",
  "description": "Support group for mothers in South Mumbai",
  "primary_category": "locality",
  "custom_category_label": null,
  "locality_label": "South Mumbai",
  "city": "Mumbai",
  "state": "Maharashtra",
  "country": "India",
  "tags": ["newborn", "local support"],
  "request_note": "Lots of users asking for this group"
}
```

Response: `201 Created` with `GroupRequest`

### 4. List My Group Requests

```http
GET /groups/requests/mine
```

Query params:

- `limit?: number` default `20`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupRequestListResponse`

### 5. Get Group Detail

```http
GET /groups/{group_id}
```

Response: `200 OK` with `Group`

Notes:

- Non-admin, non-member users can only access active groups.
- Archived groups are hidden with `404` unless current user is admin or active member.

### 6. List Group Members

```http
GET /groups/{group_id}/members
```

Response: `200 OK` with `GroupMemberListResponse`

Notes:

- Only active members or admins can access.
- Returned `user` object includes `id` and `display_name` only.
- Email is never returned here.

### 7. Join Group

```http
POST /groups/{group_id}/join
```

Request body: none

Response: `200 OK` with `GroupMembershipResponse`

Common errors:

- `404` if group does not exist
- `403` if user is banned from the group
- `409` if group is archived

### 8. Leave Group

```http
DELETE /groups/{group_id}/membership
```

Response: `204 No Content`

Notes:

- Leaving does not delete previously sent messages.

### 9. List Group Messages

```http
GET /groups/{group_id}/messages
```

Query params:

- `limit?: number` default `50`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupMessageListResponse`

Notes:

- Only active members or admins can access.
- Feed is flat and chronological.
- Only active messages are returned.

### 10. Send Group Message

```http
POST /groups/{group_id}/messages
Content-Type: application/json
```

Request body:

```json
{
  "body": "Welcome everyone",
  "attachments": [
    {
      "attachment_kind": "image",
      "url": "https://cdn.example.com/welcome.jpg",
      "mime_type": "image/jpeg",
      "file_name": "welcome.jpg",
      "size_bytes": 123456
    }
  ]
}
```

Response: `201 Created` with `GroupMessage`

Common errors:

- `404` if group does not exist
- `403` if user is not an active member
- `409` if group is archived
- `422` if both `body` and `attachments` are empty

### 11. Get My Group Chat State

```http
GET /groups/{group_id}/state
```

Response: `200 OK` with `GroupState`

Notes:

- Requires active membership.
- Creates default state if none exists yet.

### 12. Update My Group Chat State

```http
PUT /groups/{group_id}/state
Content-Type: application/json
```

Request body:

```json
{
  "last_read_message_id": "550e8400-e29b-41d4-a716-446655440000",
  "mark_all_read": false,
  "notifications_enabled": true
}
```

Response: `200 OK` with `GroupState`

Notes:

- Requires active membership.
- `mark_all_read = true` zeroes unread count and sets the latest message as read.
- `last_read_message_id = null` clears the read marker and recomputes unread count from all active messages.
- `notifications_enabled` can be toggled independently of read state.

## Admin Endpoints

### 1. List All Groups

```http
GET /admin/groups
```

Query params:

- `status?: GroupStatus`
- `search?: string`
- `primary_category?: GroupPrimaryCategory`
- `city?: string`
- `state?: string`
- `country?: string`
- `limit?: number` default `20`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupListResponse`

### 2. Create Group Directly

```http
POST /admin/groups
Content-Type: application/json
```

Request body:

```json
{
  "name": "Breastfeeding Moms Bengaluru",
  "description": "Peer support and advice",
  "primary_category": "breastfeeding",
  "custom_category_label": null,
  "locality_label": null,
  "city": "Bengaluru",
  "state": "Karnataka",
  "country": "India",
  "tags": ["lactation", "support"],
  "status": "active"
}
```

Response: `201 Created` with `Group`

### 3. Get Admin Group Detail

```http
GET /admin/groups/{group_id}
```

Response: `200 OK` with `Group`

### 4. Update Group

```http
PUT /admin/groups/{group_id}
Content-Type: application/json
```

Request body: all fields optional

```json
{
  "name": "Updated Group Name",
  "description": "Updated description",
  "status": "archived",
  "primary_category": "general_parenting",
  "custom_category_label": null,
  "locality_label": null,
  "city": "Pune",
  "state": "Maharashtra",
  "country": "India",
  "tags": ["toddlers", "weekend meetups"]
}
```

Response: `200 OK` with `Group`

Common errors:

- `404` if group does not exist
- `400` for category/location validation failures

### 5. Archive Group

```http
POST /admin/groups/{group_id}/archive
```

Request body: none

Response: `200 OK` with updated `Group`

### 6. Reactivate Group

```http
POST /admin/groups/{group_id}/reactivate
```

Request body: none

Response: `200 OK` with updated `Group`

### 7. List Group Requests

```http
GET /admin/groups/requests
```

Query params:

- `status?: GroupRequestStatus`
- `search?: string`
- `primary_category?: GroupPrimaryCategory`
- `city?: string`
- `state?: string`
- `country?: string`
- `limit?: number` default `20`, min `1`, max `100`
- `offset?: number` default `0`

Response: `200 OK` with `GroupRequestListResponse`

### 8. Approve Group Request

```http
POST /admin/groups/requests/{request_id}/approve
Content-Type: application/json
```

Request body: all fields optional

```json
{
  "name": "South Mumbai Moms",
  "description": "Approved and cleaned up by admin",
  "primary_category": "locality",
  "custom_category_label": null,
  "locality_label": "South Mumbai",
  "city": "Mumbai",
  "state": "Maharashtra",
  "country": "India",
  "tags": ["support", "newborn"],
  "resolution_note": "Approved and created"
}
```

Response: `200 OK` with `GroupRequestResolutionResponse`

Notes:

- Creates a new active group.
- Auto-joins the requester into the newly created group.

### 9. Reject Group Request

```http
POST /admin/groups/requests/{request_id}/reject
Content-Type: application/json
```

Request body:

```json
{
  "resolution_note": "Duplicate of an existing group"
}
```

Response: `200 OK` with `GroupRequestResolutionResponse`

### 10. Merge Group Request Into Existing Group

```http
POST /admin/groups/requests/{request_id}/merge
Content-Type: application/json
```

Request body:

```json
{
  "target_group_id": "550e8400-e29b-41d4-a716-446655440000",
  "resolution_note": "Merged into existing active group"
}
```

Response: `200 OK` with `GroupRequestResolutionResponse`

Common errors:

- `404` if request or target group does not exist
- `409` if request is not pending or target group is not active

### 11. List Banned Members

```http
GET /admin/groups/{group_id}/bans
```

Response: `200 OK` with:

```json
{
  "items": [
    {
      "id": "uuid",
      "group_id": "uuid",
      "user_id": "uuid",
      "status": "banned",
      "joined_at": null,
      "created_at": "2026-07-02T10:00:00Z",
      "updated_at": "2026-07-02T10:00:00Z",
      "user": {
        "id": "uuid",
        "display_name": "Jane Doe"
      }
    }
  ],
  "total": 1
}
```

### 12. Ban Member

```http
POST /admin/groups/{group_id}/members/{user_id}/ban
Content-Type: application/json
```

Request body:

```json
{
  "ban_reason": "Repeated spam"
}
```

Response: `200 OK` with `GroupMembershipResponse`

### 13. Unban Member

```http
DELETE /admin/groups/{group_id}/members/{user_id}/ban
```

Response: `200 OK` with `GroupMembershipResponse`

Notes:

- Unbanning changes membership status to `left`.
- User must explicitly join again to become active.

### 14. Remove Message

```http
DELETE /admin/groups/{group_id}/messages/{message_id}?removal_reason=Spam
```

Response: `200 OK` with `GroupMessage`

Notes:

- This is a soft remove.
- Removed messages are marked `status = removed`.
- Normal group message feed does not return removed messages.

## Frontend Integration Notes

### Discovery Screen

- Use `GET /groups`
- Filter using `primary_category`, `tag`, `city`, `state`, and `country`
- Show `member_count`, `membership_status`, and `can_join`

### Group Detail Screen

- Use `GET /groups/{group_id}`
- If `can_join = true`, show Join CTA
- If `membership_status = active`, show Messages and Members tabs

### Membership Rules

- `membership_status = null` means user has never joined
- `membership_status = left` means user can rejoin
- `membership_status = banned` means hide join action
- `can_join` is the safest join-button flag to use

### Messaging UI

- Use `GET /groups/{group_id}/messages` for the feed
- Use `POST /groups/{group_id}/messages` to send
- Backend does not upload files; frontend must upload elsewhere first, then pass attachment URL metadata

### Privacy

- Never expect email in group member or sender/requester summary payloads
- Group member lists are only visible to members or admins

### Suggested Frontend Types

- `Group`
- `GroupMembershipResponse`
- `GroupMember`
- `GroupMessage`
- `GroupRequest`
- `GroupRequestResolutionResponse`
