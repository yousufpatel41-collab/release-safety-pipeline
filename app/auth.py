"""Small demo authentication boundary: per-tenant JWTs and slow salted password hashes.

The caller NEVER selects its tenant in /ask. An authenticated user's tenant comes
from the server-side users configuration, and the JWT is signed and verified.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

ISSUER = "release-safety-runbook"
AUDIENCE = "runbook-api"
PBKDF2_ROUNDS = 310_000
BEARER = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class Principal:
    username: str
    tenant: str


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, count, salt, expected = password_hash.split("$")
        if algorithm != "pbkdf2_sha256" or not 200_000 <= int(count) <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(count))
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError):
        return False


def _secret() -> str:
    secret = os.environ.get("AUTH_JWT_SECRET", "")
    if len(secret.encode()) < 32:
        raise RuntimeError("AUTH_JWT_SECRET must be set to >=32 bytes; refusing insecure JWT")
    return secret


def _users() -> dict:
    try:
        users = json.loads(os.environ.get("RUNBOOK_USERS_JSON", "{}"))
        if not isinstance(users, dict):
            return {}
        return users
    except json.JSONDecodeError:
        return {}


def issue_token(req: LoginRequest) -> dict:
    users = _users()
    account = users.get(req.username)
    # Uniform verification work for unknown users; avoid revealing which accounts exist.
    dummy = hash_password("unusable-dummy-password", salt=b"0123456789abcdef")
    value = account.get("password_hash", dummy) if isinstance(account, dict) else dummy
    if not verify_password(req.password, value) or not isinstance(account, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    tenant = account.get("tenant", "")
    if not isinstance(tenant, str) or not tenant or tenant == "shared":
        raise HTTPException(status_code=403, detail="Account is not assigned to a tenant")
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": req.username,
            "tenant": tenant,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 15 * 60,
        },
        _secret(),
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": 900}


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = jwt.decode(
            credentials.credentials,
            _secret(),
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub", "tenant", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    username, tenant = claims.get("sub"), claims.get("tenant")
    account = _users().get(username)
    # Recheck trusted directory: revoking a user or changing tenant takes effect immediately.
    if (
        not isinstance(account, dict)
        or not isinstance(tenant, str)
        or not hmac.compare_digest(str(account.get("tenant", "")), tenant)
    ):
        raise HTTPException(status_code=401, detail="Account revoked or changed")
    return Principal(username=username, tenant=tenant)
