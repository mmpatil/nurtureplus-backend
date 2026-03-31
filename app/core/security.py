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
from app.schemas.user import User as UserSchema

logger = logging.getLogger(__name__)


# Initialize Firebase Admin SDK
def init_firebase():
    """Initialize Firebase Admin SDK from service account JSON."""
    creds_path = settings.google_application_credentials
    if not os.path.exists(creds_path):
        logger.warning(f"Service account JSON not found at {creds_path}")
        return
    
    try:
        if not firebase_admin._apps:
            creds = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(creds)
            logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")


# Initialize Firebase on module load
init_firebase()


async def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase ID token and return decoded claims.
    
    Args:
        token: Firebase ID token from Authorization header
        
    Returns:
        Decoded token claims including uid
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        decoded_token = auth.verify_id_token(token)
        firebase_uid = decoded_token.get("uid")
        logger.info(f"Firebase token verified for user: {firebase_uid}")
        return decoded_token
    except auth.ExpiredSignInError as e:
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


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_dev_uid: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user.
    
    If DEV_BYPASS_AUTH is enabled, uses X-Dev-Uid header.
    Otherwise, verifies Firebase token from Authorization header.
    
    Args:
        authorization: Authorization header (Bearer <token>)
        x_dev_uid: Development user ID (only if DEV_BYPASS_AUTH enabled)
        db: Database session
        
    Returns:
        User object from database
        
    Raises:
        HTTPException: If authentication fails
    """
    firebase_uid: Optional[str] = None
    
    # Dev bypass for testing
    if settings.dev_bypass_auth and x_dev_uid:
        logger.info(f"Using dev bypass auth with user: {x_dev_uid}")
        firebase_uid = x_dev_uid
    elif authorization:
        # Extract bearer token
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
            )
        
        token = parts[1]
        decoded = await verify_firebase_token(token)
        firebase_uid = decoded.get("uid")
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
    
    # Fetch user from database, create if doesn't exist (idempotent)
    from sqlalchemy import select
    
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user (idempotent session creation)
        user = User(firebase_uid=firebase_uid)
        db.add(user)
        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"User created - firebase_uid={firebase_uid}, internal_id={user.id}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user session",
            )
    else:
        logger.info(f"User session retrieved - firebase_uid={firebase_uid}, internal_id={user.id}")
    
    return user
