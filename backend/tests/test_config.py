"""Configuration unit tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.core.config import PROJECT_ROOT, Settings


def test_default_settings_load_without_local_env() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "FreightGuard AI API"
    assert settings.anomaly_threshold_percent == 20.0


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test FreightGuard")
    monkeypatch.setenv("PORT", "9001")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test FreightGuard"
    assert settings.port == 9001


def test_negative_anomaly_threshold_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(anomaly_threshold_percent=-0.1, _env_file=None)


def test_relative_paths_resolve_from_project_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.input_data_dir == (PROJECT_ROOT / "backend/data/input").resolve()
    assert settings.output_data_dir == (PROJECT_ROOT / "backend/data/output").resolve()


def test_absolute_paths_are_preserved(tmp_path: Path) -> None:
    settings = Settings(input_data_dir=tmp_path, _env_file=None)

    assert settings.input_data_dir == tmp_path.resolve()
