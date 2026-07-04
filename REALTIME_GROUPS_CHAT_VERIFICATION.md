# Realtime Groups Chat Verification Report

Date: 2026-07-03

This report verifies the Firestore layer used by the iOS Groups chat realtime listeners.

## Latest Status

Updated after remediation attempt:

1. The missing Firestore member doc has been backfilled and verified.
2. The backend now self-heals missing member docs when an active member calls `GET /groups/{group_id}/state`.
3. Firestore rules deployment is still blocked by IAM: the backend service account lacks `firebaserules.releases.create`.

## Original Result

REST is not the problem.

The concrete backend-side issues found are:

1. The required Firestore member doc was missing for the active joined user. This has now been fixed for the current active membership.
2. The Firebase project appears to have no Firestore rules release deployed.

These two findings explain the current symptoms:

- `Instant updates unavailable`
- `Realtime status unavailable`

## Verified Facts

### 1. Firebase project alignment

The iOS app and backend are pointed at the same Firebase project.

iOS app:

- file: `/Users/manalimpatil/git/nurtureplus-ios/nurtureplus/nurtureplus/GoogleService-Info.plist`
- `PROJECT_ID = nurture-plus-deployment-ej0gq2`

Backend config used for verification:

- file: `/Users/manalimpatil/git/nurtureplus-backend/.env`
- `FIREBASE_SERVICE_ACCOUNT_JSON.project_id = nurture-plus-deployment-ej0gq2`

Conclusion:

- No evidence of a cross-project mismatch in the checked backend config and iOS app config.

### 2. Real active DB membership used for verification

Verified active membership in the configured database:

- `group_id = 432dc935-fbd2-4239-8c32-78644b69442f`
- `group_name = Breastfeeding`
- `email = mmpatil34@gmail.com`
- `firebase_uid = AVhyaFRHLUak0dsIFaOhXXiHSpE2`
- `joined_at = 2026-07-04 01:14:27.930368+00:00`
- `message_count = 3`

### 3. Firestore member doc check

Checked path:

- `/groups/432dc935-fbd2-4239-8c32-78644b69442f/members/AVhyaFRHLUak0dsIFaOhXXiHSpE2`

Original result:

- `member_exists = false`

Current result after backfill:

- `member_exists = true`

Current data:

```json
{
  "user_id": "21cfcacd-5e17-4d49-9e4a-05dff0e84b79",
  "status": "active",
  "joined_at": "2026-07-04T01:14:27Z",
  "firebase_uid": "AVhyaFRHLUak0dsIFaOhXXiHSpE2",
  "is_admin": true
}
```

Conclusion:

- This specific missing member-doc issue has been fixed for the verified active membership.
- The backend now also recreates this doc on `GET /groups/{group_id}/state` for active members.

### 4. Firestore state doc check

Checked path:

- `/users/AVhyaFRHLUak0dsIFaOhXXiHSpE2/group_states/432dc935-fbd2-4239-8c32-78644b69442f`

Result:

- `state_exists = true`

Observed data:

```json
{
  "unread_count": 0,
  "notifications_enabled": true,
  "last_activity_at": "2026-07-04T05:45:29.658868Z",
  "last_read_message_id": "161728a5-2036-45e1-bb3d-64238e874d17"
}
```

Conclusion:

- Backend is writing group-state docs to the expected path.
- If the state listener is still denied, rules are a stronger suspect than missing data for this path.

### 5. Firestore message doc check

Checked latest message path:

- `/groups/432dc935-fbd2-4239-8c32-78644b69442f/messages/161728a5-2036-45e1-bb3d-64238e874d17`

Result:

- `message_exists = true`

Observed data:

```json
{
  "attachments": [],
  "body": "Hello",
  "reply_to_message_id": null,
  "sender_user_id": "21cfcacd-5e17-4d49-9e4a-05dff0e84b79",
  "status": "active",
  "updated_at": "2026-07-04T05:45:29Z",
  "created_at": "2026-07-04T05:45:29Z",
  "group_id": "432dc935-fbd2-4239-8c32-78644b69442f",
  "id": "161728a5-2036-45e1-bb3d-64238e874d17",
  "reply_preview": null,
  "sender": {
    "display_name": null,
    "id": "21cfcacd-5e17-4d49-9e4a-05dff0e84b79"
  }
}
```

Conclusion:

- Backend is writing message docs to the expected Firestore path.
- Realtime message failure is therefore not caused by missing message docs.

### 6. Broader DB vs Firestore mirror comparison

Compared all active group memberships in the configured database against Firestore.

Observed:

- `group=Breastfeeding`
- `group_id=432dc935-fbd2-4239-8c32-78644b69442f`
- `email=mmpatil34@gmail.com`
- `firebase_uid=AVhyaFRHLUak0dsIFaOhXXiHSpE2`
- `member_exists=false`
- `state_exists=true`

At the time of verification there was one active membership, and it was missing its Firestore member doc.

Conclusion:

- The missing membership-doc problem is real and present for the currently active joined user.

### 7. Firestore rules deployment check

Queried the Firebase Rules API for releases in project `nurture-plus-deployment-ej0gq2`.

Observed releases:

- only a Storage rules release was returned
- no Firestore rules release was returned

Observed release:

```json
{
  "name": "projects/nurture-plus-deployment-ej0gq2/releases/firebase.storage/nurture-plus-deployment-ej0gq2.firebasestorage.app",
  "rulesetName": "projects/nurture-plus-deployment-ej0gq2/rulesets/0af03e45-696d-4c9f-a59f-71e854d51727",
  "createTime": "2026-04-13T06:00:17.138039Z",
  "updateTime": "2026-04-13T06:00:17.138039Z"
}
```

Conclusion:

- There is strong evidence that Firestore rules have not been deployed in this project.
- If Firestore rules are absent or default-deny, the state listener can fail even when the `group_states` doc exists.

## Most Likely Root Causes

### Root cause 1: Missing member-doc mirror

The backend has a real active membership in Postgres, but the required Firestore member doc is missing:

- DB membership exists
- Firestore message doc exists
- Firestore state doc exists
- Firestore member doc does not exist

This directly explained the message listener failure for:

- `groups/{groupId}/messages`

Status:

- Fixed for the verified active membership.
- A code-level self-heal was added so active members recreate their member doc when loading group state.

### Root cause 2: Firestore rules not deployed

The project appears to have no Firestore rules release.

This strongly explains the state listener failure for:

- `users/{firebaseUid}/group_states/{groupId}`

because the state doc exists, but the listener is still being denied.

Status:

- Still blocked.
- A ruleset was successfully created, but publishing a Firestore release failed with `403 PERMISSION_DENIED`.
- Required permission missing from the backend service account: `firebaserules.releases.create`.

## What Was Not Verified

- Deployed backend logs were not available from this workspace, so Firestore sync exceptions were not log-verified.
- No live iOS-authenticated read was executed from the app runtime itself during this verification.

## Recommended Fix Order

1. Grant the backend service account a role that includes `firebaserules.releases.create`, such as Firebase Rules Admin, or deploy the rules from a Firebase Console/CLI account that already has that permission.
2. Deploy Firestore rules from `firestore.groups.rules`.
3. Re-test join, state listener, and message listener in the iOS app.

## Expected Outcome After Fix

For the verified active user/group pair, these paths should all exist and be readable under the deployed rules:

- `/groups/432dc935-fbd2-4239-8c32-78644b69442f/members/AVhyaFRHLUak0dsIFaOhXXiHSpE2`
- `/groups/432dc935-fbd2-4239-8c32-78644b69442f/messages/{messageId}`
- `/users/AVhyaFRHLUak0dsIFaOhXXiHSpE2/group_states/432dc935-fbd2-4239-8c32-78644b69442f`

Once those conditions are true:

- realtime message subscription should start working
- realtime state subscription should start working
