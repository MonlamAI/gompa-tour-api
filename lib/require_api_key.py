import hmac
import os
from typing import Optional
from fastapi import Header, HTTPException


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    expected = os.getenv("API_ACCESS_KEY") or os.getenv("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="API_ACCESS_KEY is not configured on the server",
        )

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_admin_key:
        token = x_admin_key.strip()

    if not token or len(token) != len(expected) or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
