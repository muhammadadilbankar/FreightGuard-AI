"""Portable fingerprints and check helpers for evaluation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..core.config import PROJECT_ROOT, Settings
from ..domain.evaluation import (
    CheckStatus,
    EnvironmentFingerprint,
    EvaluationCheck,
    EvaluationDomain,
    FileFingerprint,
)


def fingerprint_file(path: Path, *, root: Path = PROJECT_ROOT) -> FileFingerprint:
    data = Path(path).read_bytes()
    try:
        relative = Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = Path(path).name
    return FileFingerprint(
        relative_path=relative,
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
    )


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def configuration_payload(settings: Settings, mode: str) -> dict[str, Any]:
    return {
        "anomaly_threshold_percent": settings.anomaly_threshold_percent,
        "history_window": 8,
        "route_semantics": "directional-origin-destination",
        "week_semantics": "monday-through-sunday",
        "retrieval": {
            "top_k": settings.retrieval_top_k,
            "rrf_k": settings.retrieval_rrf_k,
            "sparse_weight": settings.retrieval_sparse_weight,
            "dense_weight": settings.retrieval_dense_weight,
        },
        "embedding": {
            "name": settings.embedding_model_name,
            "revision": settings.embedding_model_revision,
        },
        "evidence_gate_policy": "fg-evidence-v1",
        "global_magnitude_tolerance_percent": settings.global_magnitude_tolerance_percent,
        "root_cause": {
            "policy_version": "fg-root-cause-v1",
            "min_current_category_shipments": settings.root_cause_min_current_category_shipments,
            "min_reference_category_shipments": settings.root_cause_min_reference_category_shipments,
            "min_lead_abs_effect": settings.root_cause_min_lead_abs_effect,
            "min_lead_abs_share_pct": settings.root_cause_min_lead_abs_share_pct,
            "max_leads_per_lens": settings.root_cause_max_leads_per_lens,
            "metric_highlight_percent": settings.root_cause_metric_highlight_percent,
            "reconstruction_tolerance": settings.root_cause_reconstruction_tolerance,
        },
        "investigation_assistant": {
            "mode": "template",
            "planner_version": settings.assistant_planner_version,
            "policy_version": settings.assistant_policy_version,
            "max_steps": settings.assistant_max_plan_steps,
            "max_result_limit": settings.assistant_max_result_limit,
        },
        "explanation_mode": mode,
        "prompt_version": settings.explanation_prompt_version,
        "fallback_template_version": "fg-fallback-v1",
        "csv_contract_version": "1.0",
    }


def configuration_fingerprint(settings: Settings, mode: str) -> str:
    return canonical_sha256(configuration_payload(settings, mode))


def environment_fingerprint(settings: Settings, mode: str) -> EnvironmentFingerprint:
    packages = (
        "pandas",
        "numpy",
        "pydantic",
        "scikit-learn",
        "sentence-transformers",
        "openai",
    )
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    lock = PROJECT_ROOT / "backend" / "requirements.txt"
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    try:
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError):
        dirty = False
    return EnvironmentFingerprint(
        python=sys.version.replace("\n", " "),
        implementation=platform.python_implementation(),
        operating_system=platform.system(),
        architecture=platform.machine(),
        timezone=os.environ.get("TZ", "UTC"),
        locale=locale.setlocale(locale.LC_ALL, None),
        dependency_versions=versions,
        dependency_lock_sha256=fingerprint_file(lock).sha256 if lock.exists() else None,
        embedding_model=settings.embedding_model_name,
        embedding_revision=settings.embedding_model_revision,
        explanation_mode=mode,
        prompt_version=settings.explanation_prompt_version,
        provider_identity="template"
        if mode == "template"
        else settings.explanation_provider,
        git_commit=commit,
        dirty_worktree=dirty,
    )


def check(
    check_id: str,
    domain: EvaluationDomain,
    description: str,
    passed: bool,
    *,
    expected: Any = None,
    actual: Any = None,
    blocking: bool = True,
    details: tuple[str, ...] = (),
) -> EvaluationCheck:
    return EvaluationCheck(
        check_id=check_id,
        domain=domain,
        description=description,
        blocking=blocking,
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        expected=expected,
        actual=actual,
        details=details,
    )
