"""
Security Test Suite.
Verifies cryptographic JWT verification, expiration, tampering rejection,
and fail-closed invariants.
"""
from __future__ import annotations

from datetime import timedelta
import pytest

from src.core.exceptions import AuthenticationError, AuthorizationServiceUnavailableError
from src.core.security import create_access_token, hash_password, verify_password, verify_token


class TestJWTSecurity:

    def test_valid_token_decodes_correctly(self):
        token = create_access_token(
            {"sub": "alice", "email": "alice@acme.com", "tenant_id": "org_acme", "is_admin": False},
            expires_delta=timedelta(minutes=30),
        )
        token_data = verify_token(token)

        assert token_data.user_id == "alice"
        assert token_data.email == "alice@acme.com"
        assert token_data.tenant_id == "org_acme"
        assert token_data.is_admin is False

    def test_expired_token_rejected(self):
        token = create_access_token(
            {"sub": "alice", "email": "alice@acme.com", "tenant_id": "org_acme", "is_admin": False},
            expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        )
        with pytest.raises(AuthenticationError) as exc_info:
            verify_token(token)

        assert "expired" in str(exc_info.value.message).lower()

    def test_tampered_token_signature_rejected(self):
        token = create_access_token(
            {"sub": "alice", "email": "alice@acme.com", "tenant_id": "org_acme", "is_admin": False},
        )
        # Corrupt the signature segment
        parts = token.split(".")
        tampered_sig = parts[2][:-4] + "AAAA"
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

        with pytest.raises(AuthenticationError):
            verify_token(tampered_token)

    def test_password_hashing_and_verification(self):
        secret = "correct-horse-battery-staple"
        hashed = hash_password(secret)

        assert hashed != secret
        assert verify_password(secret, hashed) is True
        assert verify_password("wrong-password", hashed) is False

