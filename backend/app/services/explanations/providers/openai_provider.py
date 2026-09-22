"""OpenAI Responses API adapter isolated from domain orchestration."""

from time import perf_counter
from typing import Any

from ....domain.explanations import (
    ExplanationFailureCode,
    ExplanationPrompt,
    GeneratedExplanation,
    ProviderCapabilities,
    ProviderGenerationResult,
    ProviderIdentity,
    TokenUsage,
)
from ..errors import ProviderCallError, ProviderConfigurationError


class OpenAIExplanationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        temperature: float = 0,
        supports_temperature: bool = False,
        client: Any | None = None,
    ) -> None:
        if not api_key or not model.strip():
            raise ProviderConfigurationError(
                "Live OpenAI generation requires credentials and a model."
            )
        self._identity = ProviderIdentity(provider="openai", model=model)
        self._supports_temperature = supports_temperature
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        if client is None:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
            except Exception as exc:
                raise ProviderConfigurationError(
                    "Unable to initialize the OpenAI provider."
                ) from exc
        self._client = client

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            structured_output=True,
            configurable_temperature=self._supports_temperature,
            usage_reporting=True,
        )

    def generate(
        self,
        prompt: ExplanationPrompt,
        response_model: type[GeneratedExplanation],
    ) -> ProviderGenerationResult:
        kwargs: dict[str, Any] = {
            "model": self.identity.model,
            "instructions": prompt.instructions,
            "input": prompt.canonical_payload,
            "text_format": response_model,
            "max_output_tokens": self._max_output_tokens,
            "store": False,
        }
        if self._supports_temperature:
            kwargs["temperature"] = self._temperature
        started = perf_counter()
        try:
            response = self._client.responses.parse(**kwargs)
        except Exception as exc:
            raise _translate_provider_error(exc) from exc
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        refusal = _find_refusal(response)
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None and not isinstance(parsed, response_model):
            parsed = response_model.model_validate(parsed)
        return ProviderGenerationResult(
            parsed=parsed,
            refusal=refusal,
            usage=_map_usage(getattr(response, "usage", None)),
            provider_request_id=getattr(response, "id", None),
            latency_ms=latency_ms,
        )


def _find_refusal(response: Any) -> str | None:
    for output in getattr(response, "output", ()) or ():
        for content in getattr(output, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                return "provider_refusal"
    return None


def _map_usage(usage: Any) -> TokenUsage:
    if usage is None:
        return TokenUsage()
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    cached = int(getattr(input_details, "cached_tokens", 0) or 0)
    reasoning_raw = getattr(output_details, "reasoning_tokens", None)
    reasoning = int(reasoning_raw) if reasoning_raw is not None else None
    total = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    return TokenUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning,
        total_tokens=total,
    )


def _translate_provider_error(exc: Exception) -> ProviderCallError:
    name = type(exc).__name__.casefold()
    if "timeout" in name:
        return ProviderCallError(ExplanationFailureCode.PROVIDER_TIMEOUT, transient=True)
    if "ratelimit" in name or "rate_limit" in name:
        return ProviderCallError(
            ExplanationFailureCode.PROVIDER_RATE_LIMITED, transient=True
        )
    if "connection" in name or "internalserver" in name:
        return ProviderCallError(
            ExplanationFailureCode.PROVIDER_UNAVAILABLE, transient=True
        )
    if "authentication" in name or "permission" in name:
        return ProviderCallError(
            ExplanationFailureCode.CREDENTIALS_MISSING, transient=False
        )
    return ProviderCallError(
        ExplanationFailureCode.PROVIDER_PROTOCOL_ERROR, transient=False
    )
