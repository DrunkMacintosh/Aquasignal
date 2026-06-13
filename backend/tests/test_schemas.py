"""Public API contract details in models/schemas.py."""

import pytest
from pydantic import ValidationError

from models.schemas import LoginRequest, RegisterRequest


def test_register_email_is_normalized_to_lowercase():
    request = RegisterRequest(
        email="Officer@Example.COM", password="correct horse battery staple"
    )
    assert request.email == "officer@example.com"


def test_login_email_is_normalized_to_lowercase():
    request = LoginRequest(email="Staff@Example.COM", password="whatever-pw")
    assert request.email == "staff@example.com"


def test_register_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password="short")


def test_register_rejects_password_over_72_bytes():
    # 36 chars but 86 UTF-8 bytes -- the bcrypt cap is in BYTES.
    multibyte = "m" * 11 + "ま" * 25
    with pytest.raises(ValidationError):
        RegisterRequest(email="a@example.com", password=multibyte)


def test_register_accepts_minimum_valid_password():
    request = RegisterRequest(email="a@example.com", password="a" * 12)
    assert request.full_name == ""
