import jwt
import pytest

from app.core.security import TokenType, create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("correct-password")
    assert hashed != "correct-password"
    assert verify_password("correct-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_create_and_decode_access_token():
    token = create_token("user-123", TokenType.ACCESS, extra_claims={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == TokenType.ACCESS.value
    assert payload["role"] == "admin"


def test_decode_token_rejects_tampered_token():
    token = create_token("user-123", TokenType.ACCESS)
    with pytest.raises(jwt.PyJWTError):
        decode_token(token + "tampered")
