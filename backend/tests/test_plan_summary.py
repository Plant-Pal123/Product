"""Adapter tests using httpx.MockTransport - no live network calls."""

import json

import httpx
import pytest

from app.services.plan_summary import DeepseekConfigError, DeepseekRequestError, generate_ai_summary

BASE_URL = "https://api.deepseek.com"
CONTENT = {
    "timeline": {"sow_date": "2026-09-27", "harvest_date": "2026-12-06", "days_to_harvest": 70},
    "soil_effect": {"current": {"n": 40, "p": 20, "k": 30, "ph": 6.0}},
    "amendments": [{"nutrient": "n", "action": "add", "amount_kg_per_ha": 10.0, "cost": 15.0}],
    "finances": {"estimated_yield": 1.0, "revenue": 100.0, "crop_cost": 50.0, "amendment_cost": 15.0, "margin": 35.0},
    "heuristics": ["Sow within the next 14 days."],
}


def _model_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})


def test_generate_ai_summary_parses_documented_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return _model_response({
            "narrative": "A short summary.",
            "agronomic_notes": ["Watch for aphids."],
            "finance_commentary": "Margin is healthy.",
        })

    summary = generate_ai_summary(
        crop_name="carrot",
        content=CONTENT,
        api_key="test-key",
        base_url=BASE_URL,
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
    )

    assert summary["narrative"] == "A short summary."
    assert summary["agronomic_notes"] == ["Watch for aphids."]
    assert summary["finance_commentary"] == "Margin is healthy."


def test_generate_ai_summary_requires_api_key():
    with pytest.raises(DeepseekConfigError):
        generate_ai_summary(
            crop_name="carrot",
            content=CONTENT,
            api_key=None,
            base_url=BASE_URL,
            model="deepseek-chat",
            transport=httpx.MockTransport(lambda r: httpx.Response(200)),
        )


def test_generate_ai_summary_raises_config_error_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_api_key"})

    with pytest.raises(DeepseekConfigError):
        generate_ai_summary(
            crop_name="carrot",
            content=CONTENT,
            api_key="bad-key",
            base_url=BASE_URL,
            model="deepseek-chat",
            transport=httpx.MockTransport(handler),
        )


def test_generate_ai_summary_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(500)
        return _model_response({"narrative": "ok", "agronomic_notes": [], "finance_commentary": "ok"})

    generate_ai_summary(
        crop_name="carrot",
        content=CONTENT,
        api_key="test-key",
        base_url=BASE_URL,
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
    )
    assert calls["n"] == 2


def test_generate_ai_summary_raises_on_malformed_model_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    with pytest.raises(DeepseekRequestError):
        generate_ai_summary(
            crop_name="carrot",
            content=CONTENT,
            api_key="test-key",
            base_url=BASE_URL,
            model="deepseek-chat",
            transport=httpx.MockTransport(handler),
        )


def test_generate_ai_summary_raises_on_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(DeepseekRequestError):
        generate_ai_summary(
            crop_name="carrot",
            content=CONTENT,
            api_key="test-key",
            base_url=BASE_URL,
            model="deepseek-chat",
            transport=httpx.MockTransport(handler),
        )
