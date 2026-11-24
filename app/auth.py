from contextvars import ContextVar
from uuid import UUID
import httpx
from fastapi import HTTPException

current_user = ContextVar("current_user")

async def verify_user(project_url, publishable_key, bearer, transport=None):
    if not bearer.startswith("Bearer ") or not bearer[7:].strip():
        raise HTTPException(401, "User access token required")
    try:
        async with httpx.AsyncClient(timeout=10, transport=transport) as client:
            response = await client.get(project_url + "/auth/v1/user", headers={"apikey":publishable_key, "Authorization":bearer})
    except httpx.RequestError:
        raise HTTPException(503, "Authentication service unavailable") from None
    if response.status_code in (401,403):
        raise HTTPException(401, "Invalid or expired user session")
    if response.status_code != 200:
        raise HTTPException(503, "Authentication service unavailable")
    try:
        return str(UUID(response.json()["id"]))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, "Invalid authentication service response") from None
