from __future__ import annotations
"""Firebase authentication and security utilities."""
import logging
import os
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
import firebase_admin
from firebase_admin import credentials, auth

from app.core.config import settings
from app.db.session import get_db
from app.models.users import User

logger = logging.getLogger(__name__)


# Initialize Firebase Admin SDK
def init_firebase():
    """Initialize Firebase Admin SDK from env var JSON or file path."""
    import json

    if firebase_admin._apps:
        return

    try:
        json_content = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        if json_content:
            creds = credentials.Certificate(json.loads(json_content))
            firebase_admin.initialize_app(creds)
            logger.info("Firebase Admin SDK initialized from env var")
            return

        creds_path = settings.google_application_credentials
        if os.path.exists(creds_path):
            creds = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(creds)
            logger.info("Firebase Admin SDK initialized from file")
        else:
            logger.warning(
                f"No Firebase credentials found (checked env var and {creds_path})"
            )
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


init_firebase()


async def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token and return decoded claims.

    Returns decoded token claims including uid, email, name, and
    sign_in_provider (used to detect anonymous accounts).
    """
    try:
        decoded_token = auth.verify_id_token(token)
        logger.info(f"Firebase token verified for user: {decoded_token.get('uid')}")
        return decoded_token
    except auth.ExpiredIdTokenError as e:
        logger.warning(f"Expired Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
        )


def _is_anonymous_from_claims(decoded: dict) -> bool:
    """
    Return True if the Firebase token belongs to an anonymous user.

    Anonymous sign-ins have firebase.sign_in_provider == "anonymous".
    """
    firebase_info = decoded.get("firebase", {})
    return firebase_info.get("sign_in_provider") == "anonymous"


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_dev_uid: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get (or create) the current authenticated user.

    Dev bypass: if DEV_BYPASS_AUTH=true, use X-Dev-Uid header.
    Production: verify Firebase Bearer token.

    Updates email / display_name / is_anonymous on every login so the
    User row stays fresh.
    """
    from sqlalchemy import select

    firebase_uid: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    is_anonymous: bool = False

    if settings.dev_bypass_auth and x_dev_uid:
        logger.info(f"Using dev bypass auth with user: {x_dev_uid}")
        firebase_uid = x_dev_uid
        # Dev users are treated as non-anonymous permanent accounts
    elif authorization:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
            )

        decoded = await verify_firebase_token(parts[1])
        firebase_uid = decoded.get("uid")
        email = decoded.get("email")
        display_name = decoded.get("name")
        is_anonymous = _is_anonymous_from_claims(decoded)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization",
        )

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            display_name=display_name,
            is_anonymous=is_anonymous,
        )
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
            logger.info(
                f"User created - firebase_uid={firebase_uid}, internal_id={user.id}, "
                f"anonymous={is_anonymous}"
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user session",
            )
    else:
        # Refresh mutable fields from latest token claims
        changed = False
        if email is not None and user.email != email:
            user.email = email
            changed = True
        if display_name is not None and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if user.is_anonymous != is_anonymous:
            user.is_anonymous = is_anonymous
            changed = True

        if changed:
            await db.commit()
            await db.refresh(user)

        logger.info(
            f"User session retrieved - firebase_uid={firebase_uid}, internal_id={user.id}"
        )

    return user
