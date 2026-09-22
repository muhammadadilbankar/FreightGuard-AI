"""Canonical filenames, columns, values, and ingestion result types."""

from dataclasses import dataclass

import pandas as pd

from ...schemas.ingestion import ValidationReport

SHIPMENTS_DATASET = "shipments"
CONTEXT_NOTE_DATASET = "context_notes"
OUTPUT_CONTRACT_DATASET = "output_contract"

SHIPMENTS_FILENAME = "shipment_records.csv"
CONTEXT_NOTES_FILENAME = "context_notes.csv"
OUTPUT_CONTRACT_FILENAME = "sample_output_format_v2.csv"

SHIPMENT_COLUMNS = (
    "shipment_id",
    "origin",
    "destination",
    "route_type",
    "material",
    "quantity_tonnes",
    "distance_km",
    "freight_cost_inr",
    "shipment_date",
    "transporter",
)
SHIPMENT_DERIVED_COLUMNS = ("route", "week_of", "tonne_km")
SHIPMENT_IDENTIFIER_COLUMN = "shipment_id"
SHIPMENT_TEXT_COLUMNS = (
    "shipment_id",
    "origin",
    "destination",
    "route_type",
    "material",
    "transporter",
)
SHIPMENT_NUMERIC_COLUMNS = (
    "quantity_tonnes",
    "distance_km",
    "freight_cost_inr",
)
ALLOWED_ROUTE_TYPES = frozenset({"Short", "Medium", "Long"})

CONTEXT_NOTE_COLUMNS = ("note_id", "date", "applies_to", "note")
CONTEXT_NOTE_IDENTIFIER_COLUMN = "note_id"
CONTEXT_NOTE_TEXT_COLUMNS = ("note_id", "applies_to", "note")

OUTPUT_COLUMNS = (
    "route",
    "week_of",
    "cost_per_tonne_km",
    "vs_own_history",
    "vs_similar_routes",
    "flagged",
    "matched_note_id",
    "reason",
)


@dataclass(frozen=True, slots=True)
class InputBundle:
    """Validated, normalized inputs consumed by all later phases."""

    shipments: pd.DataFrame
    context_notes: pd.DataFrame
    output_columns: tuple[str, ...]
    reports: tuple[ValidationReport, ...]
