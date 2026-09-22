"""Copy safety and shipment derivation tests."""

from pathlib import Path

import pandas as pd
import pytest

from backend.app.services.ingestion.loaders import load_shipments
from backend.app.services.ingestion.normalization import normalize_shipments

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _frame(date_value: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "shipment_id": "S-1",
                "origin": " A ",
                "destination": " B ",
                "route_type": "Short",
                "material": " M ",
                "quantity_tonnes": "1.25",
                "distance_km": "2.5",
                "freight_cost_inr": "10.0",
                "shipment_date": date_value,
                "transporter": " T ",
            }
        ]
    )


@pytest.mark.parametrize(
    ("shipment_date", "expected_monday"),
    [
        ("2024-01-01", "2024-01-01"),
        ("2024-01-02", "2024-01-01"),
        ("2024-01-03", "2024-01-01"),
        ("2024-01-04", "2024-01-01"),
        ("2024-01-05", "2024-01-01"),
        ("2024-01-06", "2024-01-01"),
        ("2024-01-07", "2024-01-01"),
        ("2024-01-08", "2024-01-08"),
    ],
)
def test_every_day_maps_to_the_correct_monday(
    shipment_date: str, expected_monday: str
) -> None:
    normalized = normalize_shipments(_frame(shipment_date))

    assert normalized.loc[0, "week_of"] == pd.Timestamp(expected_monday)


def test_normalization_is_directional_trimmed_and_copy_based() -> None:
    raw = pd.concat([_frame("2024-01-01"), _frame("2024-01-02")], ignore_index=True)
    raw.loc[1, "shipment_id"] = "S-2"
    raw.loc[1, "origin"] = " B "
    raw.loc[1, "destination"] = " A "
    original = raw.copy(deep=True)

    normalized = normalize_shipments(raw)

    assert normalized["route"].tolist() == ["A-B", "B-A"]
    assert normalized["shipment_id"].tolist() == ["S-1", "S-2"]
    assert normalized.loc[0, "tonne_km"] == 3.125
    pd.testing.assert_frame_equal(raw, original)


def test_loading_does_not_change_fixture_bytes() -> None:
    path = FIXTURES / "shipments_valid_minimal.csv"
    before = path.read_bytes()

    frame, _ = load_shipments(path)

    assert path.read_bytes() == before
    assert frame["shipment_id"].tolist() == ["SHP-A", "SHP-B"]
