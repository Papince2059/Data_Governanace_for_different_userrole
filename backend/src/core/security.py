"""
JWT and password security utilities.

Responsibilities
----------------
- Hash and verify bcrypt passwords.
- Create signed JWT access tokens.
- Verify / decode JWT tokens, returning a strongly-typed TokenData object.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return *True* if *plain* matches the stored *hashed* password."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token data model
# ---------------------------------------------------------------------------


@dataclass
class TokenData:
    """Decoded and validated claims from a JWT access token."""

    user_id: str
    email: str
    tenant_id: str
    is_admin: bool
    exp: datetime
    iat: datetime
    jti: str  # JWT ID – used for token revocation tracking


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    data:
        Must include at minimum ``sub`` (user_id), ``email``, ``tenant_id``,
        and ``is_admin``.  Additional keys are merged into the payload.
    expires_delta:
        How long until the token expires.  Defaults to the value from
        :func:`get_settings`.

    Returns
    -------
    str
        A compact, URL-safe signed JWT string.
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(tz=timezone.utc)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        **data,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


def verify_token(token: str) -> TokenData:
    """
    Verify the signature, expiry, and algorithm of a JWT access token.

    Parameters
    ----------
    token:
        The raw JWT string (without the ``Bearer `` prefix).

    Returns
    -------
    TokenData
        A fully-populated :class:`TokenData` object on success.

    Raises
    ------
    AuthenticationError
        If the token is expired, has an invalid signature, is missing
        required claims, or uses an unexpected algorithm.
    """
    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
    except ExpiredSignatureError:
        raise AuthenticationError(
            message="Token has expired",
            error_code="TOKEN_EXPIRED",
        ) from None
    except JWTError as exc:
        raise AuthenticationError(
            message=f"Token validation failed: {exc}",
            error_code="TOKEN_INVALID",
        ) from exc

    # --- Validate required claims ---
    missing: list[str] = []
    for claim in ("sub", "email", "tenant_id", "exp", "iat", "jti"):
        if claim not in payload:
            missing.append(claim)

    if missing:
        raise AuthenticationError(
            message=f"Token is missing required claims: {', '.join(missing)}",
            error_code="TOKEN_MISSING_CLAIMS",
        )

    # jose already validated exp, but we still want a typed datetime object
    exp_raw = payload["exp"]
    iat_raw = payload["iat"]

    # jose may return int timestamps; convert to aware datetime
    if isinstance(exp_raw, (int, float)):
        exp_dt = datetime.fromtimestamp(exp_raw, tz=timezone.utc)
    else:
        exp_dt = exp_raw  # type: ignore[assignment]

    if isinstance(iat_raw, (int, float)):
        iat_dt = datetime.fromtimestamp(iat_raw, tz=timezone.utc)
    else:
        iat_dt = iat_raw  # type: ignore[assignment]

    return TokenData(
        user_id=str(payload["sub"]),
        email=str(payload["email"]),
        tenant_id=str(payload["tenant_id"]),
        is_admin=bool(payload.get("is_admin", False)),
        exp=exp_dt,
        iat=iat_dt,
        jti=str(payload["jti"]),
    )
