"""Validation CLI status and exit-code tests."""

import shutil
from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.services.ingestion.contracts import (
    CONTEXT_NOTES_FILENAME,
    OUTPUT_CONTRACT_FILENAME,
    SHIPMENTS_FILENAME,
)
from backend.scripts.validate_inputs import main

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _copy_valid_inputs(target: Path) -> None:
    shutil.copyfile(FIXTURES / "shipments_valid_minimal.csv", target / SHIPMENTS_FILENAME)
    shutil.copyfile(
        FIXTURES / "context_notes_valid_minimal.csv", target / CONTEXT_NOTES_FILENAME
    )
    shutil.copyfile(
        FIXTURES / "output_contract_valid.csv", target / OUTPUT_CONTRACT_FILENAME
    )


def test_cli_returns_zero_for_valid_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _copy_valid_inputs(tmp_path)

    result = main(Settings(input_data_dir=tmp_path, _env_file=None))

    assert result == 0
    assert "Result: PASS" in capsys.readouterr().out


def test_cli_returns_two_for_missing_file(tmp_path: Path) -> None:
    assert main(Settings(input_data_dir=tmp_path, _env_file=None)) == 2


def test_cli_returns_one_for_invalid_data(tmp_path: Path) -> None:
    _copy_valid_inputs(tmp_path)
    shipment_path = tmp_path / SHIPMENTS_FILENAME
    shipment_path.write_text(
        shipment_path.read_text(encoding="utf-8").replace("12.25", "0"),
        encoding="utf-8",
    )

    assert main(Settings(input_data_dir=tmp_path, _env_file=None)) == 1
