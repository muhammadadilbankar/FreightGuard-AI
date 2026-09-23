from dataclasses import replace
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.domain.evidence import EvidenceVerdict
from backend.app.domain.root_cause import (
    DecompositionLens,
    RootCauseAnalysis,
    SupportLevel,
)
from backend.app.main import ServiceOverrides, create_app
from backend.app.services.root_cause.reference_window import resolve_reference_weeks
from backend.app.services.root_cause.serialization import serialize_root_causes
from backend.app.services.root_cause.service import RootCausePolicy, _decompose
from backend.app.state.run_coordinator import RunCoordinator
from backend.app.state.snapshot_store import SnapshotStore


def _frame(rows: list[tuple[str, str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["shipment_id", "transporter", "tonne_km", "freight_cost_inr"]
    ).assign(material="M")


def test_both_lenses_reconstruct_and_preserve_entry_exit() -> None:
    current = _frame([("c1", "A", 60.0, 180.0), ("c2", "C", 40.0, 160.0)])
    references = {
        date(2024, 1, 1): _frame(
            [("h1", "A", 50.0, 100.0), ("h2", "B", 50.0, 100.0)]
        ),
        date(2024, 1, 8): _frame(
            [("h3", "A", 40.0, 80.0), ("h4", "B", 60.0, 120.0)]
        ),
    }
    gap = 3.4 - 2.0
    result = _decompose("transporter", current, references, gap, RootCausePolicy())
    assert result.reconstructed_gap == pytest.approx(gap)
    assert abs(result.reconstruction_error) <= 1e-9
    by_category = {item.category: item for item in result.contributions}
    assert by_category["C"].entry_effect > 0
    assert by_category["B"].exit_effect < 0


def test_reference_window_is_exact_available_history_without_lookahead() -> None:
    weekly = pd.DataFrame(
        {
            "route": ["R"] * 11,
            "route_type": ["Short"] * 11,
            "week_of": pd.date_range("2024-01-01", periods=11, freq="7D"),
        }
    ).drop(index=[4])
    selected = resolve_reference_weeks(
        weekly, route="R", route_type="Short", week_of=date(2024, 3, 11)
    )
    assert len(selected) == 8
    assert date(2024, 1, 29) not in selected
    assert all(week < date(2024, 3, 11) for week in selected)


def _analysis() -> RootCauseAnalysis:
    lens = DecompositionLens(
        lens="transporter",
        target_gap=0.0,
        reconstructed_gap=0.0,
        reconstruction_error=0.0,
        contributions=(),
    )
    return RootCauseAnalysis(
        candidate_key="R1|2024-01-08",
        route="R1",
        route_type="Short",
        week_of=date(2024, 1, 8),
        reference_weeks=(date(2024, 1, 1),),
        reference_week_count=1,
        support_level=SupportLevel.LIMITED,
        current_cost_per_tonne_km=2.0,
        own_history_baseline=2.0,
        target_gap=0.0,
        transporter=lens,
        material=DecompositionLens(
            lens="material",
            target_gap=0.0,
            reconstructed_gap=0.0,
            reconstruction_error=0.0,
            contributions=(),
        ),
        operational_metrics=(),
        caveats=("Descriptive only.",),
    )


def test_models_reject_non_finite_values_and_serialization_is_stable() -> None:
    analysis = _analysis()
    assert serialize_root_causes((analysis,)) == serialize_root_causes((analysis,))
    with pytest.raises(ValidationError):
        RootCauseAnalysis.model_validate(
            {**analysis.model_dump(), "target_gap": float("nan")}
        )


def test_root_cause_endpoint_availability_and_typed_errors(snapshot_factory) -> None:
    original = snapshot_factory()
    analysis = _analysis()
    unexplained = replace(
        original.anomalies[0],
        verdict=EvidenceVerdict.UNEXPLAINED,
        matched_note_id=None,
        supporting_note_ids=(),
        operational_root_cause_available=True,
    )
    available = replace(
        original,
        anomalies=(unexplained,),
        root_causes=original.freeze_root_causes({analysis.candidate_key: analysis}),
    )
    app = create_app(
        Settings(_env_file=None),
        ServiceOverrides(
            snapshot_store=SnapshotStore(available),
            run_coordinator=RunCoordinator(),
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        success = client.get("/api/anomalies/R1/2024-01-08/root-cause")
        missing = client.get("/api/anomalies/missing/2024-01-08/root-cause")
    assert success.status_code == 200
    assert success.json()["meta"]["snapshot_id"] == available.snapshot_id
    assert success.json()["data"]["canonical_verdict"] == "unexplained"
    assert missing.status_code == 404

    app = create_app(
        Settings(_env_file=None),
        ServiceOverrides(
            snapshot_store=SnapshotStore(original), run_coordinator=RunCoordinator()
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        not_applicable = client.get("/api/anomalies/R1/2024-01-08/root-cause")
    assert not_applicable.status_code == 409
    assert not_applicable.json()["error"]["code"] == "root_cause_not_applicable"
