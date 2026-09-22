"""Copy-based normalization and allowed Phase 2 shipment derivations."""

import pandas as pd

from .contracts import (
    CONTEXT_NOTE_COLUMNS,
    SHIPMENT_COLUMNS,
    SHIPMENT_DERIVED_COLUMNS,
    SHIPMENT_NUMERIC_COLUMNS,
)


def normalize_shipments(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized copy with route, Monday week, and tonne-km fields."""
    normalized = frame.loc[:, SHIPMENT_COLUMNS].copy(deep=True)
    for column in (
        "shipment_id",
        "origin",
        "destination",
        "route_type",
        "material",
        "transporter",
    ):
        normalized[column] = normalized[column].str.strip()
    for column in SHIPMENT_NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column]).astype(float)
    normalized["shipment_date"] = pd.to_datetime(
        normalized["shipment_date"], format="%Y-%m-%d", errors="raise"
    ).dt.normalize()
    normalized["route"] = normalized["origin"] + "-" + normalized["destination"]
    normalized["week_of"] = normalized["shipment_date"] - pd.to_timedelta(
        normalized["shipment_date"].dt.weekday, unit="D"
    )
    normalized["tonne_km"] = (
        normalized["quantity_tonnes"] * normalized["distance_km"]
    )
    return normalized.loc[:, SHIPMENT_COLUMNS + SHIPMENT_DERIVED_COLUMNS]


def normalize_context_notes(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a normalized copy while preserving note wording and punctuation."""
    normalized = frame.loc[:, CONTEXT_NOTE_COLUMNS].copy(deep=True)
    normalized["note_id"] = normalized["note_id"].str.strip()
    normalized["applies_to"] = normalized["applies_to"].str.strip()
    normalized["date"] = pd.to_datetime(
        normalized["date"], format="%Y-%m-%d", errors="raise"
    ).dt.normalize()
    return normalized.loc[:, CONTEXT_NOTE_COLUMNS]
