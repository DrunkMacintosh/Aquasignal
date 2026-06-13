"""Alert subscriptions, history, acknowledgement, and the cron trigger.

Guards are applied per endpoint: subscribing, unsubscribing, and acknowledging
require a JWT; GET /alerts/history is public (viewing past alerts needs no
account); /trigger authenticates with the internal token instead.
"""

import logging
from datetime import datetime, timezone
from functools import partial

import anyio
from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from firebase_admin import messaging
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.firebase import send_push_sync
from core.queries import (
    all_districts_current_risk,
    district_exists,
    latest_observed_month,
)
from core.ratelimit import READ_RATE_LIMIT, limiter
from core.scoring import ALERT_HISTORY_LIMIT, risk_level
from core.security import get_current_user, require_internal_token
from models.db import AlertEvent, AlertSubscription
from models.schemas import (
    AcknowledgeResponse,
    AlertEventResponse,
    SubscribeRequest,
    SubscriptionResponse,
    TriggerSummary,
    UnsubscribeResponse,
)

LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

_user_guard = Depends(get_current_user)


@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_user_guard],
    summary="Register a device for district alerts",
    description=(
        "Registers an FCM device token for a district with a risk threshold "
        "(0-100). Subscribing the same token to the same district again "
        "updates the threshold instead of duplicating (upsert)."
    ),
)
async def subscribe(
    body: SubscribeRequest, db: AsyncSession = Depends(get_db)
) -> SubscriptionResponse:
    if not await district_exists(db, body.district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {body.district_name}"
        )
    stmt = (
        pg_insert(AlertSubscription)
        .values(
            device_token=body.device_token,
            district_name=body.district_name,
            threshold=body.threshold,
            is_active=True,
        )
        .on_conflict_do_update(
            constraint="uq_alert_subs_token_district",
            set_={"threshold": body.threshold, "is_active": True},
        )
        .returning(AlertSubscription)
    )
    subscription = (await db.execute(stmt)).scalar_one()
    await db.commit()
    return SubscriptionResponse.model_validate(subscription)


@router.delete(
    "/subscribe/{device_token}/{district_name}",
    response_model=UnsubscribeResponse,
    dependencies=[_user_guard],
    summary="Unregister one district for a device",
    description="Removes the given device's subscription to one district only.",
)
async def unsubscribe_district(
    device_token: str = Path(min_length=8, max_length=512),
    district_name: str = Path(min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    result = await db.execute(
        delete(AlertSubscription).where(
            AlertSubscription.device_token == device_token,
            AlertSubscription.district_name == district_name,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No subscription for this device and district",
        )
    return UnsubscribeResponse(device_token=device_token, removed=result.rowcount)


@router.delete(
    "/subscribe/{device_token}",
    response_model=UnsubscribeResponse,
    dependencies=[_user_guard],
    summary="Unregister a device",
    description="Removes ALL district subscriptions for the given FCM token.",
)
async def unsubscribe(
    device_token: str = Path(min_length=8, max_length=512),
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    result = await db.execute(
        delete(AlertSubscription).where(AlertSubscription.device_token == device_token)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No subscriptions for this device token"
        )
    return UnsubscribeResponse(device_token=device_token, removed=result.rowcount)


@router.get(
    "/history/{district_name}",
    response_model=list[AlertEventResponse],
    summary="Recent alert events for a district",
    description="Last 30 alert events (newest first) with acknowledgement status.",
)
@limiter.limit(READ_RATE_LIMIT)
async def alert_history(
    request: Request,  # required by slowapi to key the client IP
    district_name: str = Path(min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
) -> list[AlertEventResponse]:
    if not await district_exists(db, district_name):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown district: {district_name}"
        )
    result = await db.execute(
        select(AlertEvent)
        .where(AlertEvent.district_name == district_name)
        .order_by(AlertEvent.sent_at.desc())
        .limit(ALERT_HISTORY_LIMIT)
    )
    return [
        AlertEventResponse(
            id=event.id,
            district_name=event.district_name,
            month=event.month.strftime("%Y-%m"),
            risk_value=round(event.risk_value, 2),
            threshold=event.threshold,
            sent_at=event.sent_at,
            delivered=event.fcm_message_id is not None,
            acknowledged=event.acknowledged,
            acknowledged_at=event.acknowledged_at,
        )
        for event in result.scalars()
    ]


@router.post(
    "/acknowledge/{alert_id}",
    response_model=AcknowledgeResponse,
    dependencies=[_user_guard],
    summary="Acknowledge an alert",
    description="Marks an alert event as acknowledged. Idempotent.",
)
async def acknowledge(
    alert_id: int, db: AsyncSession = Depends(get_db)
) -> AcknowledgeResponse:
    event = await db.get(AlertEvent, alert_id)
    if event is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Unknown alert id: {alert_id}"
        )
    if not event.acknowledged:
        event.acknowledged = True
        event.acknowledged_at = datetime.now(timezone.utc)
        await db.commit()
    return AcknowledgeResponse(id=event.id, acknowledged_at=event.acknowledged_at)


@router.post(
    "/trigger",
    response_model=TriggerSummary,
    dependencies=[Depends(require_internal_token)],
    summary="Evaluate subscriptions and send FCM pushes (internal)",
    description=(
        "Called by monthly_cron.py after re-scoring. Computes each district's "
        "area-weighted current risk, compares it against every active "
        "subscription's threshold, and sends one FCM notification per breach. "
        "Idempotent per month: a subscription that already has an alert event "
        "for the current month is skipped. Authenticated via X-Internal-Token."
    ),
)
async def trigger_alerts(db: AsyncSession = Depends(get_db)) -> TriggerSummary:
    month = await latest_observed_month(db)
    if month is None:
        return TriggerSummary(
            subscriptions_evaluated=0,
            thresholds_breached=0,
            notifications_sent=0,
            send_failures=0,
            deactivated_tokens=0,
        )

    district_risk = await all_districts_current_risk(db, month)
    subscriptions = (
        (
            await db.execute(
                select(AlertSubscription).where(AlertSubscription.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    already_alerted: set[int] = set(
        (
            await db.execute(
                select(AlertEvent.subscription_id).where(AlertEvent.month == month)
            )
        )
        .scalars()
        .all()
    )

    breached = sent = failed = deactivated = 0
    for sub in subscriptions:
        risk = district_risk.get(sub.district_name)
        if risk is None or risk < sub.threshold or sub.id in already_alerted:
            continue
        breached += 1
        fcm_message_id: str | None = None
        try:
            fcm_message_id = await anyio.to_thread.run_sync(
                partial(
                    send_push_sync,
                    sub.device_token,
                    f"AquaSignal: {sub.district_name} risk is {risk_level(risk)}",
                    (
                        f"Groundwater risk reached {risk:.0f}/100 "
                        f"(your threshold: {sub.threshold:.0f})."
                    ),
                    {
                        "district": sub.district_name,
                        "month": month.strftime("%Y-%m"),
                        "risk": f"{risk:.1f}",
                    },
                )
            )
            sent += 1
        except messaging.UnregisteredError:
            # Stale token: stop trying it in future runs.
            sub.is_active = False
            deactivated += 1
        except Exception:  # noqa: BLE001 -- one bad token must not kill the run
            LOG.exception("FCM send failed for subscription %d", sub.id)
            failed += 1
        # Record the breach even when delivery failed (fcm_message_id NULL)
        # so /alerts/history is a faithful audit of threshold crossings.
        db.add(
            AlertEvent(
                subscription_id=sub.id,
                district_name=sub.district_name,
                month=month,
                risk_value=risk,
                threshold=sub.threshold,
                fcm_message_id=fcm_message_id,
            )
        )
    await db.commit()
    return TriggerSummary(
        month=month.strftime("%Y-%m"),
        subscriptions_evaluated=len(subscriptions),
        thresholds_breached=breached,
        notifications_sent=sent,
        send_failures=failed,
        deactivated_tokens=deactivated,
    )
