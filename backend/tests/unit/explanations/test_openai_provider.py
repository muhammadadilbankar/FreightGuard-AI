"""Mocked OpenAI SDK boundary tests."""

from types import SimpleNamespace

import pytest

from backend.app.domain.evidence import EvidenceVerdict
from backend.app.domain.explanations import ExplanationPrompt, GeneratedExplanation
from backend.app.services.explanations import ProviderCallError
from backend.app.services.explanations.providers import OpenAIExplanationProvider


class Responses:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def test_openai_adapter_maps_parsed_usage_and_omits_temperature() -> None:
    parsed = GeneratedExplanation(
        route="A-B",
        week_of="2025-01-06",
        verdict=EvidenceVerdict.JUSTIFIED,
        cited_note_ids=("N1",),
        reason="N1 provides route-specific evidence of increased transport cost this week.",
    )
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        input_tokens_details=SimpleNamespace(cached_tokens=2),
        output_tokens_details=SimpleNamespace(reasoning_tokens=1),
    )
    responses = Responses(SimpleNamespace(output_parsed=parsed, output=[], usage=usage, id="r1"))
    provider = OpenAIExplanationProvider(
        api_key="test",
        model="configured-model",
        timeout_seconds=1,
        max_output_tokens=100,
        supports_temperature=False,
        client=SimpleNamespace(responses=responses),
    )
    result = provider.generate(ExplanationPrompt(prompt_version="v", instructions="i", canonical_payload="{}"), GeneratedExplanation)
    assert result.parsed == parsed
    assert result.usage.cached_input_tokens == 2
    assert result.provider_request_id == "r1"
    assert "temperature" not in responses.kwargs
    assert responses.kwargs["store"] is False
    assert "tools" not in responses.kwargs


def test_openai_adapter_maps_refusal_and_timeout() -> None:
    refusal = SimpleNamespace(type="refusal")
    response = SimpleNamespace(
        output_parsed=None,
        output=[SimpleNamespace(content=[refusal])],
        usage=None,
        id="r2",
    )
    provider = OpenAIExplanationProvider(
        api_key="test", model="m", timeout_seconds=1, max_output_tokens=100,
        client=SimpleNamespace(responses=Responses(response)),
    )
    result = provider.generate(ExplanationPrompt(prompt_version="v", instructions="i", canonical_payload="{}"), GeneratedExplanation)
    assert result.refusal == "provider_refusal"

    class APITimeoutError(Exception):
        pass

    failing = OpenAIExplanationProvider(
        api_key="test", model="m", timeout_seconds=1, max_output_tokens=100,
        client=SimpleNamespace(responses=Responses(error=APITimeoutError())),
    )
    with pytest.raises(ProviderCallError) as captured:
        failing.generate(ExplanationPrompt(prompt_version="v", instructions="i", canonical_payload="{}"), GeneratedExplanation)
    assert captured.value.transient is True
