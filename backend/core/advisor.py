"""AI water-planning advisor: structured intake + deep-analysis report.

The frontend assembles a compact ``AdvisorSnapshot`` of a district's prediction
data (Option A thin proxy). The advisor works in two steps, both relayed to
OpenRouter's OpenAI-compatible chat-completions API (the key never leaves the
server):

1. ``generate_questions`` -- a few short, tailored intake questions.
2. ``generate_report`` -- a deep, *structured* report (fixed JSON schema)
   grounded in the data + the user's answers.

Both steps force JSON output (``response_format``) and parse defensively: a
free model that returns slightly-off JSON is coerced into shape rather than
crashing the request, and a totally unparseable response degrades gracefully.

``AdvisorError`` wraps every upstream failure so the router can answer with a
single 502; ``AdvisorRateLimited`` is split out so a transient 429 becomes a
"busy, retry" 429 instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from core.config import Settings
from models.schemas import AdvisorAnswer, AdvisorNeed, AdvisorSnapshot

LOG = logging.getLogger("aquasignal.advisor")

_TEMPERATURE = 0.4
_TIMEOUT_SECONDS = 60.0
# Free models share an upstream pool and return 429 transiently ("retry
# shortly"). Retry a couple of times with a short backoff before giving up; the
# total stays well inside the client's request timeout.
_RETRY_BACKOFF_SECONDS = (1.0, 2.0)

# Bounds: questions are tiny, the report is longer but still capped.
_QUESTIONS_MAX_TOKENS = 600
_REPORT_MAX_TOKENS = 1600

# Intake size + answer caps mirror the schema; keep prompts (and cost) bounded.
MIN_QUESTIONS = 3
MAX_QUESTIONS = 5

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

# Static fallback questions per need, used when the model's question JSON can't
# be parsed. Mirrors lib/advisor.js FALLBACK_QUESTIONS.
FALLBACK_QUESTIONS: dict[AdvisorNeed, list[dict[str, str]]] = {
    "water_sustainability": [
        {"id": "water_source", "question": "What is your main water source?", "hint": "well, surface, piped"},
        {"id": "well_depth", "question": "If you use a well, how deep is it?", "hint": "approx. metres"},
        {"id": "monthly_use", "question": "Roughly how much water do you use per month?", "hint": "m3 or 'unsure'"},
        {"id": "main_concern", "question": "What is your biggest water concern?", "hint": "shortage, cost, quality"},
    ],
    "agriculture": [
        {"id": "land_area", "question": "How large is the land you irrigate?", "hint": "hectares"},
        {"id": "crops", "question": "What crops do you grow?", "hint": "e.g. rice, vegetables"},
        {"id": "water_source", "question": "What is your irrigation water source?", "hint": "well, canal, river"},
        {"id": "irrigation_method", "question": "How do you irrigate?", "hint": "flood, drip, sprinkler"},
    ],
    "urban_supply": [
        {"id": "population", "question": "How many people does the supply serve?", "hint": "households or people"},
        {"id": "source", "question": "What is the supply source?", "hint": "wells, surface, mixed"},
        {"id": "storage", "question": "What storage capacity do you have?", "hint": "m3 or 'none'"},
        {"id": "main_concern", "question": "What is the biggest supply concern?", "hint": "shortage, leakage, quality"},
    ],
    "industrial": [
        {"id": "process_use", "question": "What is water used for in your process?", "hint": "cooling, washing, product"},
        {"id": "monthly_use", "question": "Roughly how much water per month?", "hint": "m3 or 'unsure'"},
        {"id": "source", "question": "What is your water source?", "hint": "well, municipal, surface"},
        {"id": "reuse", "question": "Do you recycle or reuse any water?", "hint": "yes/no, how"},
    ],
}

# The exact report shape the model must return. Kept as a constant so the prompt
# and the tests reference one source of truth.
_REPORT_SCHEMA = (
    "{\n"
    '  "headline": "one-line verdict, max 12 words",\n'
    '  "outlook": "one short tag, e.g. Stable / Cautious / At risk / Critical",\n'
    '  "situation_assessment": "2-4 sentences interpreting the data for this goal",\n'
    '  "your_context": "1-2 sentences summarising the user\'s situation",\n'
    '  "key_findings": ["3-5 short, data-grounded insights"],\n'
    '  "action_plan": [\n'
    '    {"timeframe": "Immediate (0-1 month)", "actions": ["..."]},\n'
    '    {"timeframe": "Short-term (1-3 months)", "actions": ["..."]},\n'
    '    {"timeframe": "Medium-term (3-6 months)", "actions": ["..."]}\n'
    "  ],\n"
    '  "risks": ["what could go wrong or what to watch"],\n'
    '  "monitoring": ["metrics to track and when to revisit"]\n'
    "}"
)


class AdvisorError(RuntimeError):
    """Any failure talking to OpenRouter (timeout, non-2xx, malformed body)."""


class AdvisorRateLimited(AdvisorError):
    """OpenRouter (or its upstream provider) is rate-limiting us (HTTP 429).

    Distinct from AdvisorError so the router can answer 429 ("busy, retry") --
    a transient, retryable condition -- instead of a 502.
    """


# --------------------------------------------------------------------------- #
# Snapshot -> context block
# --------------------------------------------------------------------------- #


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


def _context_block(
    district_name: str, need: AdvisorNeed, snapshot: AdvisorSnapshot
) -> str:
    """Shared role + location + goal + data preamble for both prompts."""
    goal_label, goal_focus = NEED_GUIDANCE[need]
    data_block = _format_data_block(snapshot) or "- No prediction data was provided."
    return (
        "You are AquaSignal's water-planning advisor for Vietnam. AquaSignal "
        "forecasts groundwater well-failure risk from satellite data.\n\n"
        f"LOCATION: {district_name}\n"
        f"USER'S GOAL: {goal_label}.\n"
        f"FOCUS: {goal_focus}\n\n"
        "PREDICTION DATA FOR THIS LOCATION:\n"
        f"{data_block}\n"
    )


# --------------------------------------------------------------------------- #
# Prompts (structured instructions)
# --------------------------------------------------------------------------- #


def build_questions_prompt(
    district_name: str, need: AdvisorNeed, snapshot: AdvisorSnapshot
) -> str:
    return (
        _context_block(district_name, need, snapshot)
        + "\n"
        + (
            f"TASK: Produce {MIN_QUESTIONS} to {MAX_QUESTIONS} SHORT intake "
            "questions whose answers you need to write a tailored water-use plan "
            "for this goal and location. Each question must be answerable in one "
            "short phrase (e.g. land area, crop or usage type, water source and "
            "well depth, current monthly usage, budget or constraints). Do NOT "
            "ask for anything already given in the data above.\n"
            "Return ONLY a JSON object, no prose, no markdown:\n"
            '{"questions":[{"id":"snake_case_id","question":"the question",'
            '"hint":"short example answer"}]}'
        )
    )


def build_report_prompt(
    district_name: str,
    need: AdvisorNeed,
    snapshot: AdvisorSnapshot,
    answers: list[AdvisorAnswer],
) -> str:
    answer_lines = (
        "\n".join(f"- {a.question}: {a.answer}" for a in answers)
        or "- (the user provided no answers)"
    )
    return (
        _context_block(district_name, need, snapshot)
        + "\nUSER'S ANSWERS:\n"
        + answer_lines
        + "\n\n"
        + (
            "TASK: Write a DEEP, specific water-use plan for this goal and "
            "location as a structured report. Ground every statement in the data "
            "and the user's answers; be concrete and realistic, not generic. You "
            "are advisory only -- include a reminder to confirm critical "
            "decisions with local water authorities (in risks or monitoring).\n"
            "Return ONLY a JSON object of exactly this shape, no prose, no "
            "markdown:\n"
            f"{_REPORT_SCHEMA}"
        )
    )


# --------------------------------------------------------------------------- #
# OpenRouter call (shared by both steps)
# --------------------------------------------------------------------------- #


async def _complete(
    messages: list[dict[str, str]],
    *,
    settings: Settings,
    max_tokens: int,
    json_mode: bool = False,
) -> str:
    """Relay one chat-completions request and return the reply text.

    Retries transient 429s with a short backoff. Raises ``AdvisorRateLimited``
    when the provider stays rate-limited, ``AdvisorError`` for any other
    failure.
    """
    if not settings.openrouter_api_key:
        raise AdvisorError("OpenRouter API key is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_title,
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": settings.openrouter_model,
        "messages": messages,
        "temperature": _TEMPERATURE,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
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
                    "OpenRouter 429 (attempt %d): %s", attempt + 1, response.text[:300]
                )
                if attempt < len(_RETRY_BACKOFF_SECONDS):
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])
                    continue
                raise AdvisorRateLimited("model provider is rate-limited")

            LOG.warning(
                "OpenRouter returned %s: %s", response.status_code, response.text[:500]
            )
            raise AdvisorError(f"model provider returned status {response.status_code}")

    try:
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        LOG.warning("OpenRouter response was malformed: %s", exc)
        raise AdvisorError("model provider returned an unexpected response") from exc

    if not isinstance(reply, str) or not reply.strip():
        raise AdvisorError("model provider returned an empty reply")
    return reply.strip()


# --------------------------------------------------------------------------- #
# JSON parsing + normalization (free models are imprecise)
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _extract_json(text: str) -> dict | None:
    """Best-effort parse of a JSON object from a model reply: strips code
    fences, then falls back to the first ``{`` .. last ``}`` slice."""
    cleaned = _FENCE_RE.sub("", text.strip())
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return None


def _as_str_list(value, *, item_cap: int = 500, max_items: int = 12) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text[:item_cap])
        if len(out) >= max_items:
            break
    return out


def _as_phase_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    phases = []
    for item in value:
        if not isinstance(item, dict):
            continue
        actions = _as_str_list(item.get("actions"))
        if not actions:
            continue
        phases.append(
            {"timeframe": str(item.get("timeframe") or "").strip()[:80], "actions": actions}
        )
        if len(phases) >= 6:
            break
    return phases


def _normalize_report(data: dict) -> dict:
    """Coerce a parsed report dict into the AdvisorReport shape so a
    slightly-off model response never fails validation."""
    return {
        "headline": (str(data.get("headline") or "Water-use plan").strip())[:200],
        "outlook": (str(data.get("outlook") or "").strip())[:60],
        "situation_assessment": (str(data.get("situation_assessment") or "").strip())[:2000],
        "your_context": (str(data.get("your_context") or "").strip())[:2000],
        "key_findings": _as_str_list(data.get("key_findings")),
        "action_plan": _as_phase_list(data.get("action_plan")),
        "risks": _as_str_list(data.get("risks")),
        "monitoring": _as_str_list(data.get("monitoring")),
    }


def _normalize_questions(data: dict, need: AdvisorNeed) -> list[dict]:
    raw = data.get("questions") if isinstance(data, dict) else None
    questions: list[dict] = []
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            text = str(item.get("question") or "").strip()
            if not text:
                continue
            questions.append(
                {
                    "id": (str(item.get("id") or f"q{i + 1}").strip() or f"q{i + 1}")[:40],
                    "question": text[:300],
                    "hint": (str(item.get("hint")).strip()[:120] if item.get("hint") else None),
                }
            )
            if len(questions) >= MAX_QUESTIONS:
                break
    if len(questions) < MIN_QUESTIONS:
        return list(FALLBACK_QUESTIONS[need])
    return questions


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


async def generate_questions(
    district_name: str, need: AdvisorNeed, snapshot: AdvisorSnapshot, *, settings: Settings
) -> list[dict]:
    """Return 3-5 short intake questions (model-tailored, with a static
    fallback if the JSON can't be parsed)."""
    messages = [
        {"role": "system", "content": build_questions_prompt(district_name, need, snapshot)},
        {"role": "user", "content": "Generate the intake questions now."},
    ]
    for _ in range(2):  # one reparse-retry on unparseable JSON
        raw = await _complete(
            messages, settings=settings, max_tokens=_QUESTIONS_MAX_TOKENS, json_mode=True
        )
        data = _extract_json(raw)
        if data is not None:
            return _normalize_questions(data, need)
    LOG.warning("Advisor questions JSON unparseable; using fallback set")
    return list(FALLBACK_QUESTIONS[need])


async def generate_report(
    district_name: str,
    need: AdvisorNeed,
    snapshot: AdvisorSnapshot,
    answers: list[AdvisorAnswer],
    *,
    settings: Settings,
) -> dict:
    """Return a normalized structured report dict (ready for AdvisorReport)."""
    messages = [
        {
            "role": "system",
            "content": build_report_prompt(district_name, need, snapshot, answers),
        },
        {"role": "user", "content": "Write the structured report now."},
    ]
    last_raw = ""
    for _ in range(2):  # one reparse-retry on unparseable JSON
        last_raw = await _complete(
            messages, settings=settings, max_tokens=_REPORT_MAX_TOKENS, json_mode=True
        )
        data = _extract_json(last_raw)
        if data is not None:
            return _normalize_report(data)
    # Total parse failure: degrade to a minimal report rather than erroring.
    LOG.warning("Advisor report JSON unparseable; degrading to raw text")
    return _normalize_report(
        {"headline": f"Water-use plan for {district_name}", "situation_assessment": last_raw}
    )
