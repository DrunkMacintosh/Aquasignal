"""AI water-planning advisor: prompt assembly + OpenRouter proxy.

The frontend assembles a compact ``AdvisorSnapshot`` of a district's prediction
data (Option A thin proxy) and posts it with the conversation. This module turns
that snapshot into a system prompt and relays the conversation to OpenRouter's
OpenAI-compatible chat-completions API. The API key never leaves the server.

Design notes:
* The system prompt instructs the model to *analyze the data, ask about the
  user's current position, then produce a sustainable water-usage route* -- the
  three-step flow the feature is built around.
* ``AdvisorError`` wraps every upstream failure (timeout, non-2xx, malformed
  body) so the router can answer with a single 502 instead of leaking httpx
  internals to the client.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from core.config import Settings
from models.schemas import AdvisorNeed, AdvisorSnapshot

LOG = logging.getLogger("aquasignal.advisor")

# Bounded so a free-tier model returns a focused plan rather than an essay, and
# so one turn can't blow the quota.
_MAX_TOKENS = 900
_TEMPERATURE = 0.4
_TIMEOUT_SECONDS = 60.0
# Free models share an upstream pool and return 429 transiently ("retry
# shortly"). Retry a couple of times with a short backoff before giving up; the
# total stays well inside the client's request timeout.
_RETRY_BACKOFF_SECONDS = (1.0, 2.0)

# Human-readable goal + the angle the advisor should reason from. Keys match
# AdvisorNeed (schemas.py) and ADVISOR_NEEDS (frontend lib/advisor.js).
NEED_GUIDANCE: dict[AdvisorNeed, tuple[str, str]] = {
    "water_sustainability": (
        "long-term water sustainability",
        "Focus on conserving the aquifer: matching abstraction to recharge, "
        "reducing losses, and building resilience to the forecast risk trend.",
    ),
    "agriculture": (
        "agriculture and irrigation",
        "Focus on crop water demand, irrigation efficiency, and scheduling that "
        "respects the recharge outlook and the months of highest forecast risk.",
    ),
    "urban_supply": (
        "urban and domestic water supply",
        "Focus on household and municipal demand, storage, leakage reduction, "
        "and contingency for high-risk months.",
    ),
    "industrial": (
        "industrial water use",
        "Focus on process water demand, recycling/reuse, and sustainable "
        "abstraction limits given the recharge and subsidence signals.",
    ),
}


class AdvisorError(RuntimeError):
    """Any failure talking to OpenRouter (timeout, non-2xx, malformed body)."""


class AdvisorRateLimited(AdvisorError):
    """OpenRouter (or its upstream provider) is rate-limiting us (HTTP 429).

    Distinct from AdvisorError so the router can answer 429 ("busy, retry") --
    a transient, retryable condition -- instead of a 502.
    """


def _format_number(value: float | None, unit: str = "", digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{round(value, digits)}{unit}"


def _format_data_block(snapshot: AdvisorSnapshot) -> str:
    """Render the snapshot as a compact, model-readable context block."""
    lines: list[str] = []

    if snapshot.current_risk is not None or snapshot.risk_level is not None:
        risk = _format_number(snapshot.current_risk, "/100")
        band = snapshot.risk_level or "n/a"
        trend = snapshot.trend or "n/a"
        month = snapshot.latest_month or "n/a"
        lines.append(
            f"Current well-failure risk ({month}): {risk} (band: {band}, 3-month "
            f"trend: {trend})."
        )

    if snapshot.forecast:
        points = ", ".join(
            f"{p.month} {round(p.predicted_risk, 1)} "
            f"[{round(p.confidence_interval_low, 1)}-"
            f"{round(p.confidence_interval_high, 1)}]"
            for p in snapshot.forecast
        )
        lines.append(f"6-month risk forecast (predicted [CI low-high]): {points}.")

    if snapshot.history:
        recent = snapshot.history[-12:]
        series = ", ".join(f"{p.month} {round(p.risk, 1)}" for p in recent)
        lines.append(f"Recent observed risk: {series}.")

    if snapshot.satellite:
        latest = snapshot.satellite[-1]
        lines.append(
            "Latest satellite observations ("
            f"{latest.month}): GRACE anomaly {_format_number(latest.grace_anomaly, ' cm')}, "
            f"precipitation {_format_number(latest.precipitation, ' mm')}, "
            f"evapotranspiration {_format_number(latest.evapotranspiration, ' mm')}, "
            f"temperature {_format_number(latest.temperature, ' C')}, "
            f"SAR backscatter {_format_number(latest.sar_subsidence, ' dB')} "
            "(subsidence proxy, not a displacement rate)."
        )

    if snapshot.permeability_index is not None:
        lines.append(
            "Soil permeability index "
            f"{_format_number(snapshot.permeability_index, '', 2)} "
            f"(class: {snapshot.permeability_class or 'n/a'})."
        )
    if snapshot.recharge_value is not None:
        lines.append(
            "Relative recharge potential "
            f"{_format_number(snapshot.recharge_value)} "
            f"(label: {snapshot.recharge_label or 'n/a'}, net infiltration "
            f"{_format_number(snapshot.net_infiltration_mm, ' mm')}). This is a "
            "ranking indicator, not a calibrated mm/month rate."
        )

    return "\n".join(f"- {line}" for line in lines)


def build_system_prompt(
    district_name: str, need: AdvisorNeed, snapshot: AdvisorSnapshot
) -> str:
    """Assemble the system prompt: role, data context, goal, and the
    analyze -> ask -> plan flow the feature is designed around."""
    goal_label, goal_focus = NEED_GUIDANCE[need]
    data_block = _format_data_block(snapshot) or "- No prediction data was provided."

    return (
        "You are AquaSignal's water-planning advisor for Vietnam. AquaSignal "
        "forecasts groundwater well-failure risk from satellite data. You help "
        "local users plan sustainable water use for a specific location.\n\n"
        f"LOCATION: {district_name}\n"
        f"USER'S GOAL: {goal_label}.\n"
        f"FOCUS: {goal_focus}\n\n"
        "PREDICTION DATA FOR THIS LOCATION:\n"
        f"{data_block}\n\n"
        "HOW TO HELP, in order:\n"
        "1. Briefly interpret what this data means for the user's goal "
        "(2-4 sentences, plain language, no jargon dumps).\n"
        "2. Ask the user focused questions about their current position before "
        "giving a final plan -- e.g. land area, crops or usage type, water "
        "source (well depth, surface, piped), current monthly usage, and "
        "constraints. Ask only what you still need; don't re-ask answered "
        "items.\n"
        "3. Once you have enough detail, give a concrete, step-by-step route to "
        "sustain their water usage for this goal, tied to the location's risk "
        "trend and recharge outlook. Use numbered steps and realistic actions.\n\n"
        "Keep replies concise and specific to this location's data. If the data "
        "is missing, say so and reason from the goal. You are advisory only -- "
        "recommend confirming critical decisions with local water authorities."
    )


async def chat(
    messages: list[dict[str, str]], *, settings: Settings
) -> str:
    """Relay a chat-completions request to OpenRouter and return the reply text.

    ``messages`` is the full OpenAI-style list (system prompt already prepended).
    Raises ``AdvisorError`` on any upstream failure.
    """
    if not settings.openrouter_api_key:
        # Callers should gate on this, but guard anyway rather than send an
        # unauthenticated request.
        raise AdvisorError("OpenRouter API key is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_title,
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
    }
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        for attempt in range(len(_RETRY_BACKOFF_SECONDS) + 1):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                LOG.warning("OpenRouter request failed: %s", exc)
                raise AdvisorError("could not reach the model provider") from exc

            if response.status_code == httpx.codes.OK:
                break

            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                LOG.warning(
                    "OpenRouter 429 (attempt %d): %s",
                    attempt + 1,
                    response.text[:300],
                )
                if attempt < len(_RETRY_BACKOFF_SECONDS):
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])
                    continue
                raise AdvisorRateLimited("model provider is rate-limited")

            LOG.warning(
                "OpenRouter returned %s: %s", response.status_code, response.text[:500]
            )
            raise AdvisorError(
                f"model provider returned status {response.status_code}"
            )

    try:
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        LOG.warning("OpenRouter response was malformed: %s", exc)
        raise AdvisorError("model provider returned an unexpected response") from exc

    if not isinstance(reply, str) or not reply.strip():
        raise AdvisorError("model provider returned an empty reply")
    return reply.strip()
