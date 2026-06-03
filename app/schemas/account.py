"""Pydantic schemas for account deletion responses."""

from typing import Optional

from pydantic import BaseModel


class AccountDeletionResponse(BaseModel):
    """Success/failure contract for DELETE /account."""

    success: bool
    message: str
    code: Optional[str] = None

