"""API key authentication for inbound support requests."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def verify_api_key(
    api_key: str | None = Header(default=None, alias="API_KEY"),
) -> str:
    settings = get_settings()
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API_KEY header",
        )
    return api_key
