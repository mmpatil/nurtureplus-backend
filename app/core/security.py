from __future__ import annotations
"""Firebase authentication and security utilities."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
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


async def verify_firebase_token(token: str, *, check_revoked: bool = True) -> dict:
    """
    Verify Firebase ID token and return decoded claims.

    Returns decoded token claims including uid, email, name, and
    sign_in_provider (used to detect anonymous accounts).
    """
    try:
        decoded_token = auth.verify_id_token(token, check_revoked=check_revoked)
        logger.info(f"Firebase token verified for user: {decoded_token.get('uid')}")
        return decoded_token
    except auth.RevokedIdTokenError as e:
        logger.warning(f"Revoked Firebase token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked. Please sign in again.",
        )
    except auth.UserDisabledError as e:
        logger.warning(f"Disabled Firebase user token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account disabled",
        )
    except auth.UserNotFoundError as e:
        logger.warning(f"Deleted Firebase user token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists",
        )
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


def parse_bearer_token(authorization: Optional[str]) -> str:
    """Extract Bearer token from Authorization header or raise 401."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization",
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )
    return parts[1]


async def get_authenticated_identity(
    authorization: Optional[str],
    x_dev_uid: Optional[str],
) -> dict:
    """
    Return normalized auth identity from dev bypass header or Firebase token.

    Shape:
      {
        "firebase_uid": str,
        "email": Optional[str],
        "display_name": Optional[str],
        "is_anonymous": bool,
        "auth_time": Optional[datetime],
      }
    """
    if settings.dev_bypass_auth and x_dev_uid:
        logger.info(f"Using dev bypass auth with user: {x_dev_uid}")
        return {
            "firebase_uid": x_dev_uid,
            "email": None,
            "display_name": None,
            "is_anonymous": False,
            "auth_time": datetime.now(timezone.utc),
        }

    token = parse_bearer_token(authorization)
    decoded = await verify_firebase_token(token, check_revoked=True)
    firebase_uid = decoded.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    auth_time = decoded.get("auth_time")
    auth_datetime = (
        datetime.fromtimestamp(auth_time, tz=timezone.utc)
        if isinstance(auth_time, (int, float))
        else None
    )
    return {
        "firebase_uid": firebase_uid,
        "email": decoded.get("email"),
        "display_name": decoded.get("name"),
        "is_anonymous": _is_anonymous_from_claims(decoded),
        "auth_time": auth_datetime,
    }


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

    identity = await get_authenticated_identity(authorization, x_dev_uid)
    firebase_uid = identity["firebase_uid"]
    email = identity["email"]
    display_name = identity["display_name"]
    is_anonymous = identity["is_anonymous"]

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
        except IntegrityError:
            # Another request may have created the same user concurrently.
            await db.rollback()
            result = await db.execute(
                select(User).where(User.firebase_uid == firebase_uid)
            )
            user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user session",
                )
            logger.info(
                f"User session recovered after concurrent create - "
                f"firebase_uid={firebase_uid}, internal_id={user.id}"
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
