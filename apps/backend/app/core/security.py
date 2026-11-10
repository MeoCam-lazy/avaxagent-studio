"""Authentication and authorization dependencies for the control-plane API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.auth.tokens import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


class User(BaseModel):
    address: str

    @property
    def id(self) -> str:
        return self.address.lower()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized"},
        )

    payload = decode_access_token(credentials.credentials)
    address = payload.get("sub")
    if not address or not isinstance(address, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token_payload"},
        )

    return User(address=address)


CurrentUser = Annotated[User, Depends(get_current_user)]
