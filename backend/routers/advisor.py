"""AI water-planning advisor endpoints (two-step report flow).

* `GET  /advisor/config`    -- is the advisor enabled, and which model.
* `POST /advisor/questions` -- a few short, tailored intake questions.
* `POST /advisor/report`    -- a deep, structured report from the answers.

Both POSTs are thin proxies: they build prompts from the client-supplied
district snapshot, relay to OpenRouter, and return structured JSON. The API key
stays server-side; the snapshot is the same public read-only data the panel
already shows.
"""

import logging
from typing import Awaitable, TypeVar

from fastapi import APIRouter, HTTPException, Request, status

from core.advisor import (
    AdvisorError,
    AdvisorRateLimited,
    generate_questions,
    generate_report,
)
from core.config import Settings, get_settings
from core.ratelimit import ADVISOR_RATE_LIMIT, limiter
from models.schemas import (
    AdvisorConfigResponse,
    AdvisorQuestion,
    AdvisorQuestionsRequest,
    AdvisorQuestionsResponse,
    AdvisorReport,
    AdvisorReportRequest,
    AdvisorReportResponse,
)

LOG = logging.getLogger("aquasignal.advisor")

router = APIRouter(prefix="/advisor", tags=["advisor"])

T = TypeVar("T")


def _require_enabled() -> Settings:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI advisor is not configured on this server.",
        )
    return settings


async def _run(coro: Awaitable[T], *, district: str) -> T:
    """Await an advisor call, mapping upstream failures to HTTP errors: a
    transient 429 -> 429 ("busy, retry"), anything else -> 502."""
    try:
        return await coro
    except AdvisorRateLimited as exc:
        LOG.warning("Advisor rate-limited for %s: %s", district, exc)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The AI advisor is busy right now. Please try again in a moment.",
        ) from exc
    except AdvisorError as exc:
        LOG.warning("Advisor failed for %s: %s", district, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="The AI advisor is temporarily unavailable. Please try again.",
        ) from exc


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
    "/questions",
    response_model=AdvisorQuestionsResponse,
    summary="Intake questions for a water plan",
    description=(
        "Returns 3-5 short, tailored questions the advisor needs before writing "
        "a plan for the chosen need at this location. Returns 503 when no model "
        "is configured."
    ),
)
@limiter.limit(ADVISOR_RATE_LIMIT)
async def post_advisor_questions(
    request: Request,  # required by slowapi to key the client IP
    body: AdvisorQuestionsRequest,
) -> AdvisorQuestionsResponse:
    settings = _require_enabled()
    questions = await _run(
        generate_questions(
            body.district_name, body.need, body.snapshot, settings=settings
        ),
        district=body.district_name,
    )
    return AdvisorQuestionsResponse(
        questions=[AdvisorQuestion(**q) for q in questions],
        model=settings.openrouter_model,
    )


@router.post(
    "/report",
    response_model=AdvisorReportResponse,
    summary="Deep-analysis water plan report",
    description=(
        "Generates a structured water-use report for the chosen need at this "
        "location, grounded in the prediction-data snapshot and the user's "
        "answers. Returns 503 when no model is configured."
    ),
)
@limiter.limit(ADVISOR_RATE_LIMIT)
async def post_advisor_report(
    request: Request,  # required by slowapi to key the client IP
    body: AdvisorReportRequest,
) -> AdvisorReportResponse:
    settings = _require_enabled()
    report = await _run(
        generate_report(
            body.district_name,
            body.need,
            body.snapshot,
            body.answers,
            settings=settings,
            site_summary=body.site_summary,
        ),
        district=body.district_name,
    )
    return AdvisorReportResponse(report=AdvisorReport(**report), model=settings.openrouter_model)
