"""DeepSeek (OpenAI-compatible chat completions API) integration that turns a
generated future plan's JSON (app/services/plan_generator.py) into a
plain-language summary for the PDF (design.md §6, FR-5.10): a narrative
paragraph, a few agronomic notes not already computed by the heuristics, and
a one-line comment on the finance table.

This never invents numbers - the prompt hands the model the exact figures
plan_generator already computed and asks it to describe them, not recompute
them. It is additive: if no API key is configured, or the request fails, the
PDF still renders with the heuristic data alone (see routes/plans.py).
"""

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("plan_summary.deepseek")

CHAT_COMPLETIONS_PATH = "/chat/completions"

SYSTEM_PROMPT = (
    "You are an agronomy assistant writing a short section of a farm future-plan "
    "PDF. You are given the plan's already-computed data (timeline, soil nutrient "
    "gap, recommended amendments, projected finances) as JSON. Do not invent or "
    "recompute any numbers - only describe the ones given. Respond with a single "
    "JSON object with exactly these keys: "
    '"narrative" (a 2-4 sentence plain-language summary of the plan), '
    '"agronomic_notes" (a list of 1-3 short strings with general crop-care or risk '
    "notes for this crop that are NOT already covered by the given heuristics), "
    '"finance_commentary" (a single sentence plainly describing the margin/cost '
    "figures given, e.g. flagging a thin or negative margin)."
)


class DeepseekConfigError(Exception):
    """Missing API key, or DeepSeek rejected it."""


class DeepseekRequestError(Exception):
    """The request failed after retries, or the response could not be parsed."""


def _build_user_prompt(crop_name: str, content: dict[str, Any]) -> str:
    plan_data = {
        "crop": crop_name,
        "timeline": content.get("timeline", {}),
        "soil_effect": content.get("soil_effect", {}),
        "amendments": content.get("amendments", []),
        "finances": content.get("finances", {}),
        "existing_heuristics": content.get("heuristics", []),
    }
    return f"Plan data:\n{json.dumps(plan_data)}"


def generate_ai_summary(
    crop_name: str,
    content: dict[str, Any],
    api_key: str | None,
    base_url: str,
    model: str,
    timeout_seconds: float = 30.0,
    max_retries: int = 3,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Calls DeepSeek's chat completions API and returns
    {"narrative": str, "agronomic_notes": list[str], "finance_commentary": str}.

    Raises DeepseekConfigError if no key is set or DeepSeek rejects it,
    DeepseekRequestError on any other failure (network, non-200, malformed
    response) - callers should treat both as "skip the AI section", not a
    reason to fail the whole PDF (see routes/plans.py)."""

    if not api_key:
        raise DeepseekConfigError(
            "DEEPSEEK_API_KEY is not set - get a free/low-cost key at "
            "https://platform.deepseek.com/ (see backend/README.md)."
        )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(crop_name, content)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    url = base_url.rstrip("/") + CHAT_COMPLETIONS_PATH

    with httpx.Client(timeout=timeout_seconds, transport=transport) as client:
        body = _post_with_retries(client, url, payload, headers, max_retries)

    return _parse_summary(body)


def _post_with_retries(
    client: httpx.Client, url: str, payload: dict, headers: dict, max_retries: int
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            last_error = exc
            logger.warning("deepseek timeout attempt=%s/%s", attempt, max_retries)
        except httpx.TransportError as exc:
            last_error = exc
            logger.warning("deepseek transport error attempt=%s/%s: %s", attempt, max_retries, exc)
        else:
            if response.status_code == 429 or response.status_code >= 500:
                last_error = DeepseekRequestError(f"HTTP {response.status_code}")
                logger.warning("deepseek retryable status attempt=%s/%s status=%s", attempt, max_retries, response.status_code)
            elif response.status_code in (401, 403):
                raise DeepseekConfigError(f"DeepSeek rejected the API key (HTTP {response.status_code})")
            elif response.status_code != 200:
                raise DeepseekRequestError(f"HTTP {response.status_code}: {response.text[:200]}")
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise DeepseekRequestError(f"Non-JSON response: {exc}") from exc

        if attempt < max_retries:
            time.sleep(2 ** (attempt - 1))  # 1s, 2s, 4s, ...

    raise DeepseekRequestError(f"Giving up after {max_retries} attempts") from last_error


def _parse_summary(body: dict[str, Any]) -> dict[str, Any]:
    try:
        message_content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepseekRequestError(f"Unexpected response shape: missing choices[0].message.content - {exc}") from exc

    try:
        parsed = json.loads(message_content)
    except ValueError as exc:
        raise DeepseekRequestError(f"Model response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise DeepseekRequestError("Model response JSON was not an object")

    return {
        "narrative": str(parsed.get("narrative", "")).strip(),
        "agronomic_notes": [str(note).strip() for note in parsed.get("agronomic_notes", []) if str(note).strip()],
        "finance_commentary": str(parsed.get("finance_commentary", "")).strip(),
    }
