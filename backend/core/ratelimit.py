"""Shared slowapi limiter (one instance for app wiring and route decorators)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

RISK_MAP_RATE_LIMIT = "60/minute"
# General read endpoints (forecast, history, satellite, alert history): the
# same ceiling as the risk map. They are public (no auth), so the throttle is
# what stops an anonymous client from hammering them.
READ_RATE_LIMIT = "60/minute"
# Exports render CSV and (for PDF) matplotlib + ReportLab in a worker thread --
# far more expensive per call than a JSON read, so they get a tighter ceiling.
EXPORT_RATE_LIMIT = "10/minute"
# The advisor proxies to an LLM (real latency + a metered free-tier quota), so
# it gets a tighter ceiling than plain JSON reads.
ADVISOR_RATE_LIMIT = "15/minute"
LOGIN_RATE_LIMIT = "10/minute"
# Stricter than login: legitimate users register once, so a low ceiling
# mainly hurts bulk account creation and email enumeration.
REGISTER_RATE_LIMIT = "5/minute"

limiter = Limiter(key_func=get_remote_address)
