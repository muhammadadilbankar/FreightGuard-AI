"""Decimal-based externally configured model-cost estimation."""

from decimal import Decimal

from ...domain.explanations import ExplanationSettings, TokenUsage

_MILLION = Decimal(1_000_000)


def estimate_cost_usd(
    usage: TokenUsage, settings: ExplanationSettings
) -> Decimal | None:
    if usage.total_tokens == 0:
        return Decimal(0)
    input_rate = settings.input_cost_per_1m_usd
    output_rate = settings.output_cost_per_1m_usd
    if input_rate is None or output_rate is None:
        return None
    cached_rate = settings.cached_input_cost_per_1m_usd or input_rate
    non_cached = usage.input_tokens - usage.cached_input_tokens
    return (
        Decimal(non_cached) * input_rate
        + Decimal(usage.cached_input_tokens) * cached_rate
        + Decimal(usage.output_tokens) * output_rate
    ) / _MILLION
