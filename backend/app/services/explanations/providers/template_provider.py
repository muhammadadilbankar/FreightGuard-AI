"""Deterministic no-network provider for offline development and tests."""

from ....domain.evidence import EvidenceVerdict
from ....domain.explanations import (
    ExplanationPrompt,
    GeneratedExplanation,
    GroundedExplanationRequest,
    ProviderCapabilities,
    ProviderGenerationResult,
    ProviderIdentity,
    TokenUsage,
)
from ..fallbacks import render_fallback_explanation


class ReplayIdentityProvider:
    """Carries live identity in replay mode and can never make a call."""

    def __init__(self, provider: str, model: str) -> None:
        self._identity = ProviderIdentity(provider=provider, model=model)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            structured_output=True,
            configurable_temperature=False,
            usage_reporting=True,
        )

    def generate(self, prompt, response_model):
        raise AssertionError("Replay mode must never call a provider.")


class TemplateExplanationProvider:
    @property
    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(provider="template", model="deterministic-v1")

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            structured_output=True,
            configurable_temperature=False,
            usage_reporting=False,
        )

    def generate(
        self,
        prompt: ExplanationPrompt,
        response_model: type[GeneratedExplanation],
    ) -> ProviderGenerationResult:
        request = GroundedExplanationRequest.model_validate_json(prompt.canonical_payload)
        if request.verdict == EvidenceVerdict.UNEXPLAINED:
            cited = ()
        elif request.verdict == EvidenceVerdict.JUSTIFIED:
            cited = (request.selected_note_id,) if request.selected_note_id else ()
        else:
            cited = request.allowed_note_ids[:1]
        parsed = response_model(
            route=request.route,
            week_of=request.week_of,
            verdict=request.verdict,
            cited_note_ids=cited,
            reason=render_fallback_explanation(request),
        )
        return ProviderGenerationResult(parsed=parsed, usage=TokenUsage())
