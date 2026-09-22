"""Public grounded explanation generation services."""

from .cache import ExplanationCache, build_cache_key
from .costing import estimate_cost_usd
from .errors import (
    ExplanationCacheError,
    ExplanationError,
    ExplanationInputError,
    ExplanationReconciliationError,
    ExplanationValidationError,
    PromptConstructionError,
    ProviderCallError,
    ProviderConfigurationError,
)
from .fallbacks import render_fallback_explanation
from .generation import generate_explanation, generate_explanations
from .prompts import PROMPT_VERSION, build_explanation_prompt, canonical_request_json
from .requests import build_grounded_request
from .validation import validate_generated_explanation

__all__ = [
    "PROMPT_VERSION",
    "ExplanationCache",
    "ExplanationCacheError",
    "ExplanationError",
    "ExplanationInputError",
    "ExplanationReconciliationError",
    "ExplanationValidationError",
    "PromptConstructionError",
    "ProviderCallError",
    "ProviderConfigurationError",
    "build_cache_key",
    "build_explanation_prompt",
    "build_grounded_request",
    "canonical_request_json",
    "estimate_cost_usd",
    "generate_explanation",
    "generate_explanations",
    "render_fallback_explanation",
    "validate_generated_explanation",
]
