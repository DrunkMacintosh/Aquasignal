"""AI water-planning advisor endpoints.

`GET /advisor/config` lets the frontend discover whether the advisor is enabled
(an OpenRouter key is configured) so it can hide the section otherwise.

`POST /advisor/chat` is a thin proxy: it builds a system prompt from the
client-supplied district snapshot, prepends it to the conversation, relays to
OpenRouter, and returns the reply. The API key stays server-side; the data in
the snapshot is the same public read-only data the panel already shows.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from core.advisor import AdvisorError, AdvisorRateLimited, build_system_prompt, chat
from core.config import get_settings
from core.ratelimit import ADVISOR_RATE_LIMIT, limiter
from models.schemas import (
    AdvisorChatRequest,
    AdvisorChatResponse,
    AdvisorConfigResponse,
)

LOG = logging.getLogger("aquasignal.advisor")

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get(
    "/config",
    response_model=AdvisorConfigResponse,
    summary="Advisor availability",
    description=(
        "Reports whether the AI advisor is enabled (an OpenRouter key is "
        "configured server-side) and which model is active. Public so the UI "
        "can hide the advisor when it is not configured."
    ),
)
async def get_advisor_config() -> AdvisorConfigResponse:
    settings = get_settings()
    enabled = bool(settings.openrouter_api_key)
    return AdvisorConfigResponse(
        enabled=enabled,
        model=settings.openrouter_model if enabled else None,
    )


@router.post(
    "/chat",
    response_model=AdvisorChatResponse,
    summary="Chat with the water-planning advisor",
    description=(
        "Sends the conversation plus a compact district-data snapshot to the "
        "configured OpenRouter model. The model interprets the location's "
        "prediction data, asks about the user's current position, and works "
        "toward a sustainable water-usage plan for the chosen need. Returns "
        "503 when no model is configured."
    ),
)
@limiter.limit(ADVISOR_RATE_LIMIT)
async def post_advisor_chat(
    request: Request,  # required by slowapi to key the client IP
    body: AdvisorChatRequest,
) -> AdvisorChatResponse:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI advisor is not configured on this server.",
        )

    system_prompt = build_system_prompt(body.district_name, body.need, body.snapshot)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": m.role, "content": m.content} for m in body.messages)

    try:
        reply = await chat(messages, settings=settings)
    except AdvisorRateLimited as exc:
        # Transient: the (free) model's upstream pool is busy. Tell the client
        # to retry rather than implying the feature is broken.
        LOG.warning("Advisor rate-limited for %s: %s", body.district_name, exc)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The AI advisor is busy right now. Please try again in a moment.",
        ) from exc
    except AdvisorError as exc:
        LOG.warning("Advisor chat failed for %s: %s", body.district_name, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="The AI advisor is temporarily unavailable. Please try again.",
        ) from exc

    return AdvisorChatResponse(reply=reply, model=settings.openrouter_model)
