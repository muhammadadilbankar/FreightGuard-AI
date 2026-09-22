"""Typed application settings with repository-relative path resolution."""

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator
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

    @model_validator(mode="after")
    def resolve_data_paths(self) -> Self:
        """Make relative data paths stable regardless of the current directory."""
        for field_name in ("input_data_dir", "output_data_dir"):
            value = getattr(self, field_name)
            resolved = value if value.is_absolute() else PROJECT_ROOT / value
            object.__setattr__(self, field_name, resolved.resolve())
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the immutable process configuration."""
    return Settings()
