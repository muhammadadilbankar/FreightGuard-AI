"""Typed application settings with repository-relative path resolution."""

from functools import lru_cache
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Self
import math

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "FreightGuard AI API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    input_data_dir: Path = Path("backend/data/input")
    output_data_dir: Path = Path("backend/data/output")
    anomaly_threshold_percent: float = Field(default=20.0, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1)
    retrieval_rrf_k: int = Field(default=60, ge=1)
    retrieval_sparse_weight: float = Field(default=1.0, ge=0)
    retrieval_dense_weight: float = Field(default=1.0, ge=0)
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_revision: str = (
        "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    embedding_model_path: Path | None = Path(
        "backend/data/models/all-MiniLM-L6-v2"
    )
    embedding_local_only: bool = True
    global_magnitude_tolerance_percent: float = Field(default=2.0, ge=0)
    explanation_mode: str = "template"
    explanation_provider: str = "openai"
    explanation_model: str = ""
    explanation_prompt_version: str = "fg-explanation-v1"
    explanation_temperature: float = 0.0
    explanation_temperature_supported: bool = False
    explanation_max_output_tokens: int = Field(default=220, ge=64, le=2048)
    explanation_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    explanation_max_attempts: int = Field(default=2, ge=1, le=5)
    explanation_max_concurrency: int = Field(default=3, ge=1, le=16)
    explanation_cache_enabled: bool = True
    explanation_cache_path: Path = Path(
        "backend/data/output/explanation_cache.jsonl"
    )
    model_input_cost_per_1m_usd: Decimal | None = None
    model_cached_input_cost_per_1m_usd: Decimal | None = None
    model_output_cost_per_1m_usd: Decimal | None = None
    model_pricing_snapshot_date: date | None = None
    openai_api_key: SecretStr | None = None

    @field_validator("embedding_model_path", mode="before")
    @classmethod
    def empty_model_path_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "model_input_cost_per_1m_usd",
        "model_cached_input_cost_per_1m_usd",
        "model_output_cost_per_1m_usd",
        "model_pricing_snapshot_date",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def empty_optional_values_are_none(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def resolve_data_paths(self) -> Self:
        """Make relative data paths stable regardless of the current directory."""
        for field_name in (
            "input_data_dir",
            "output_data_dir",
            "embedding_model_path",
            "explanation_cache_path",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            resolved = value if value.is_absolute() else PROJECT_ROOT / value
            object.__setattr__(self, field_name, resolved.resolve())
        weights = (self.retrieval_sparse_weight, self.retrieval_dense_weight)
        if any(not math.isfinite(weight) for weight in weights):
            raise ValueError("Retrieval weights must be finite.")
        if not any(weight > 0 for weight in weights):
            raise ValueError("At least one retrieval weight must be positive.")
        if not math.isfinite(self.global_magnitude_tolerance_percent):
            raise ValueError("Global magnitude tolerance must be finite.")
        if not self.embedding_model_name.strip():
            raise ValueError("Embedding model name must not be blank.")
        if not self.embedding_model_revision.strip():
            raise ValueError("Embedding model revision must not be blank.")
        if self.explanation_mode not in {"template", "live", "replay"}:
            raise ValueError("Explanation mode must be template, live, or replay.")
        if self.explanation_provider != "openai":
            raise ValueError("Only the openai explanation provider is supported.")
        if not self.explanation_prompt_version.strip():
            raise ValueError("Explanation prompt version must not be blank.")
        if not math.isfinite(self.explanation_temperature):
            raise ValueError("Explanation temperature must be finite.")
        if not math.isfinite(self.explanation_timeout_seconds):
            raise ValueError("Explanation timeout must be finite.")
        rates = (
            self.model_input_cost_per_1m_usd,
            self.model_cached_input_cost_per_1m_usd,
            self.model_output_cost_per_1m_usd,
        )
        if any(rate is not None and (not rate.is_finite() or rate < 0) for rate in rates):
            raise ValueError("Model cost rates must be finite and non-negative.")
        if any(rate is not None for rate in rates) and self.model_pricing_snapshot_date is None:
            raise ValueError("A pricing snapshot date is required with model cost rates.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the immutable process configuration."""
    return Settings()
