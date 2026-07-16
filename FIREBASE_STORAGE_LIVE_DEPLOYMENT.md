# Live Firebase Storage Deployment

This repository contains the deployable Firebase Storage rules for the live iOS/backend project:

- Project ID: `nurture-plus-deployment-ej0gq2`
- Storage bucket: `nurture-plus-deployment-ej0gq2.firebasestorage.app`

The legacy Flutter repo under `/Users/manalimpatil/git/nurtureplus` is still wired to the older `nurture-plus-afa6a6` Firebase project. Do not deploy Storage rules for the current iOS app from that legacy tree.

## Files

- `firebase-live/.firebaserc`
- `firebase-live/firebase.json`
- `firebase-live/storage.rules`

## Behavior

The live bucket uses:

- default deny for all Storage paths
- explicit allow for `/users/{userId}/{allPaths=**}`
- read allowed under the user subtree
- write allowed only when `request.auth.uid == userId`

This matches the current iOS product-analysis upload behavior:

- `users/{firebaseUid}/food-products/package_front_photo/...`
- `users/{firebaseUid}/food-products/package_back_photo/...`

## Deploy

From the repository root, deploy the live Storage rules with a Firebase-authenticated CLI user or service account that has Firebase Rules release permissions for `nurture-plus-deployment-ej0gq2`.

Example:

```bash
cd firebase-live
firebase deploy --only storage --project nurture-plus-deployment-ej0gq2
```

If using the backend service account, ensure it has permission to publish Firebase Rules releases. A role such as Firebase Rules Admin is sufficient.
