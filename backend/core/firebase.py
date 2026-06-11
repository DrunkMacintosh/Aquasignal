"""Lazy Firebase Admin initialisation and FCM send helper.

``messaging.send()`` is a blocking HTTP call. Async endpoints must run it via
``anyio.to_thread.run_sync`` so the event loop is never blocked on Firebase.
"""

from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, messaging

from core.config import get_settings


@lru_cache(maxsize=1)
def get_firebase_app() -> firebase_admin.App:
    """Initialise the Firebase app once, on first use (not at import time,
    so the API can boot and report /health even without FCM credentials)."""
    cred = credentials.Certificate(str(get_settings().firebase_credentials_file))
    return firebase_admin.initialize_app(cred)


def send_push_sync(
    device_token: str, title: str, body: str, data: dict[str, str]
) -> str:
    """Send one FCM notification; returns the FCM message id.

    Raises ``messaging.UnregisteredError`` when the device token is stale --
    callers should deactivate the subscription in that case.
    """
    get_firebase_app()
    message = messaging.Message(
        token=device_token,
        notification=messaging.Notification(title=title, body=body),
        data=data,  # FCM requires string values
    )
    return messaging.send(message)
