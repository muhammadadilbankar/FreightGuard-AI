"""Provider-neutral grounded explanation interface."""

from typing import Protocol

from ....domain.explanations import (
    ExplanationPrompt,
    GeneratedExplanation,
    ProviderCapabilities,
    ProviderGenerationResult,
    ProviderIdentity,
)


class ExplanationProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def generate(
        self,
        prompt: ExplanationPrompt,
        response_model: type[GeneratedExplanation],
    ) -> ProviderGenerationResult: ...
