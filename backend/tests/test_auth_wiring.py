"""Authentication wiring: which routes are public vs JWT-guarded.

These assertions inspect the assembled FastAPI app's dependency tree instead of
making HTTP calls, so they need no database. They pin the contract that data
reads are public while setting/changing an alert still requires a token --
exactly the change that opened the dashboard to anonymous visitors.
"""

from fastapi.routing import APIRoute

from app import app
from core.security import get_current_user

# Every read surface a visitor browses without an account.
PUBLIC_PREFIXES = ("/risk-map", "/forecast", "/history", "/satellite", "/export")


def _route(path: str, method: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not registered: {method} {path}")


def _requires_user_auth(route: APIRoute) -> bool:
    """True if get_current_user sits anywhere in the route's dependency tree."""
    stack = list(route.dependant.dependencies)
    while stack:
        dependency = stack.pop()
        if dependency.call is get_current_user:
            return True
        stack.extend(dependency.dependencies)
    return False


def test_data_reads_are_public():
    data_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(PUBLIC_PREFIXES)
    ]
    assert data_routes, "expected risk/forecast/history/satellite/export routes"
    for route in data_routes:
        assert not _requires_user_auth(route), f"{route.path} should be public"


def test_viewing_alert_history_is_public():
    assert not _requires_user_auth(_route("/alerts/history/{district_name}", "GET"))


def test_setting_an_alert_requires_auth():
    assert _requires_user_auth(_route("/alerts/subscribe", "POST"))


def test_acknowledging_an_alert_requires_auth():
    assert _requires_user_auth(_route("/alerts/acknowledge/{alert_id}", "POST"))


def test_unsubscribing_requires_auth():
    assert _requires_user_auth(
        _route("/alerts/subscribe/{device_token}/{district_name}", "DELETE")
    )
