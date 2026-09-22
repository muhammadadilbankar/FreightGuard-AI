"""Opt-in one-packet live-provider smoke test."""

import os

import pytest

from backend.app.core.config import get_settings
from backend.app.domain.explanations import ExplanationSettings, ExplanationSource, GenerationMode
from backend.app.services.explanations import ExplanationCache, generate_explanation
from backend.app.services.explanations.providers import OpenAIExplanationProvider
from backend.tests.integration.test_evidence_pipeline_supplied_data import supplied_result


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_EXPLANATION_TESTS") != "1",
    reason="live explanation smoke test is explicitly opt-in",
)
def test_one_live_explanation_is_grounded(tmp_path) -> None:
    settings = get_settings()
    assert settings.openai_api_key is not None
    assert settings.explanation_model
    *_, evidence = supplied_result()
    packet = next(item for item in evidence.packets if item.allowed_note_ids)
    provider = OpenAIExplanationProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.explanation_model,
        timeout_seconds=min(settings.explanation_timeout_seconds, 30),
        max_output_tokens=min(settings.explanation_max_output_tokens, 220),
        temperature=settings.explanation_temperature,
        supports_temperature=settings.explanation_temperature_supported,
    )
    record = generate_explanation(
        packet,
        provider,
        ExplanationCache(tmp_path / "live-cache.jsonl"),
        ExplanationSettings(
            mode=GenerationMode.LIVE,
            prompt_version=settings.explanation_prompt_version,
            max_attempts=1,
            max_concurrency=1,
        ),
    )
    assert record.explanation_source in {ExplanationSource.MODEL, ExplanationSource.FALLBACK}
    assert set(record.cited_note_ids).issubset(set(packet.allowed_note_ids))
