from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


JWT_SECRET_ENV = "JWT_SECRET"
JWT_ALGORITHM = "HS256"


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    role: str
    claims: Dict[str, Any]


bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=False)


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _decode_segment(segment: str) -> Dict[str, Any]:
    try:
        raw = _b64url_decode(segment)
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT segment encoding.",
        ) from exc


def _get_secret() -> bytes:
    secret = os.getenv(JWT_SECRET_ENV, "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret is not configured.",
        )
    return secret.encode("utf-8")


def _verify_signature(message: bytes, signature: bytes, secret: bytes) -> None:
    expected = hmac.new(secret, message, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT signature verification failed.",
        )


def _validate_claims(payload: Dict[str, Any]) -> None:
    exp = payload.get("exp")
    if exp is not None:
        try:
            exp_value = int(exp)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT exp claim must be an integer.",
            ) from exc
        if exp_value < int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT has expired.",
            )


def _decode_jwt(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT structure.",
        )
    header_segment, payload_segment, signature_segment = parts
    header = _decode_segment(header_segment)
    payload = _decode_segment(payload_segment)
    if header.get("alg") != JWT_ALGORITHM:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported JWT algorithm.",
        )
    message = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = _b64url_decode(signature_segment)
    _verify_signature(message, signature, _get_secret())
    _validate_claims(payload)
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization credentials.",
        )
    token = credentials.credentials.strip()
    payload = _decode_jwt(token)
    subject = str(payload.get("sub") or "unknown")
    role = str(payload.get("role") or "user")
    return AuthenticatedUser(subject=subject, role=role, claims=payload)


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user
