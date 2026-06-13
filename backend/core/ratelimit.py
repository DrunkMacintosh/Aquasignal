"""Shared slowapi limiter (one instance for app wiring and route decorators)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

RISK_MAP_RATE_LIMIT = "60/minute"
LOGIN_RATE_LIMIT = "10/minute"
# Stricter than login: legitimate users register once, so a low ceiling
# mainly hurts bulk account creation and email enumeration.
REGISTER_RATE_LIMIT = "5/minute"

limiter = Limiter(key_func=get_remote_address)
