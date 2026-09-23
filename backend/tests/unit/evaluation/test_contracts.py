from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.domain.evaluation import (
    ArtifactComparison,
    CheckStatus,
    EnvironmentFingerprint,
    EvaluationCheck,
    EvaluationDomain,
    EvaluationMetric,
    EvaluationReport,
    ReproducibilityResult,
)
from backend.app.evaluation.contracts import configuration_fingerprint, fingerprint_file
from backend.app.evaluation.registry import normalize_registry


def _environment() -> EnvironmentFingerprint:
    return EnvironmentFingerprint(
        python="3",
        implementation="CPython",
        operating_system="test",
        architecture="test",
        timezone="UTC",
        locale="C",
        dependency_versions={},
        dependency_lock_sha256=None,
        embedding_model="model",
        embedding_revision="rev",
        explanation_mode="template",
        prompt_version="v1",
        provider_identity="template",
        git_commit=None,
        dirty_worktree=False,
    )


def _reproducibility() -> ReproducibilityResult:
    return ReproducibilityResult(
        formal=True,
        run_count=3,
        runs=(),
        comparisons=(
            ArtifactComparison(
                artifact_name="final_submission.csv",
                identical=True,
                hashes=("a", "a", "a"),
                byte_sizes=(1, 1, 1),
            ),
        ),
        overall_reproducible=True,
    )


def test_blocking_skip_forces_fail_and_contradictory_status_is_rejected() -> None:
    checks = (
        EvaluationCheck(
            check_id="a",
            domain=EvaluationDomain.INPUT_INTEGRITY,
            description="a",
            status=CheckStatus.SKIP,
        ),
    )
    with pytest.raises(ValueError, match="derived as fail"):
        EvaluationReport(
            overall_status="pass",
            evaluation_mode="template",
            run_count=3,
            environment=_environment(),
            inputs=(),
            configuration_fingerprint="x",
            checks=checks,
            metrics=(),
            reproducibility=_reproducibility(),
            artifacts=(),
        )


def test_registry_rejects_duplicate_ids() -> None:
    item = EvaluationCheck(
        check_id="same",
        domain=EvaluationDomain.INPUT_INTEGRITY,
        description="x",
        status=CheckStatus.PASS,
    )
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_registry((item, item), ())


def test_informational_metric_does_not_fail_report() -> None:
    metric = EvaluationMetric(
        metric_id="m",
        domain=EvaluationDomain.RETRIEVAL_QUALITY,
        value=0,
        unit="ratio",
        target=1,
        target_relation="informational",
        blocking=False,
    )
    EvaluationReport(
        overall_status="pass",
        evaluation_mode="template",
        run_count=3,
        environment=_environment(),
        inputs=(),
        configuration_fingerprint="x",
        checks=(),
        metrics=(metric,),
        reproducibility=_reproducibility(),
        artifacts=(),
    )


def test_fingerprints_are_content_and_output_path_independent(tmp_path: Path) -> None:
    path = tmp_path / "known.bin"
    path.write_bytes(b"abc")
    assert (
        fingerprint_file(path).sha256
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    one = Settings(_env_file=None, evaluation_output_root=tmp_path / "one")
    two = Settings(_env_file=None, evaluation_output_root=tmp_path / "two")
    assert configuration_fingerprint(one, "template") == configuration_fingerprint(
        two, "template"
    )
    three = Settings(
        _env_file=None,
        anomaly_threshold_percent=25,
        evaluation_output_root=tmp_path / "three",
    )
    assert configuration_fingerprint(one, "template") != configuration_fingerprint(
        three, "template"
    )
