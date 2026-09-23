"""Fresh-process three-run reproducibility harness."""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter

from ..domain.evaluation import (
    ArtifactComparison,
    ArtifactFingerprint,
    ReproducibilityResult,
    ReproducibilityRun,
)
from .outputs import evaluate_final_csv

CANONICAL_ARTIFACTS = ("final_submission.csv",)


def run_reproducibility(
    command: Sequence[str],
    run_count: int,
    output_root: Path,
    environment: Mapping[str, str],
    timeout_seconds: int,
    *,
    cwd: Path,
    authoritative_records: Sequence[Mapping[str, str]],
) -> ReproducibilityResult:
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    runs: list[ReproducibilityRun] = []
    for index in range(1, run_count + 1):
        run_id = f"run_{index:02d}"
        run_dir = output_root / "runs" / run_id
        if run_dir.exists():
            if output_root not in run_dir.parents:
                raise ValueError(
                    "Refusing to clear run directory outside evaluation root."
                )
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)
        child_env = os.environ.copy()
        child_env.update(environment)
        child_env["OUTPUT_DATA_DIR"] = str(run_dir)
        started = perf_counter()
        timed_out = False
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd,
                env=child_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            exit_code = completed.returncode
            stdout, stderr = completed.stdout[-4000:], completed.stderr[-4000:]
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 3
            stdout = (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else ""
        artifacts = []
        for name in CANONICAL_ARTIFACTS:
            path = run_dir / name
            if path.exists():
                data = path.read_bytes()
                artifacts.append(
                    ArtifactFingerprint(
                        relative_path=path.relative_to(output_root).as_posix(),
                        sha256=hashlib.sha256(data).hexdigest(),
                        byte_size=len(data),
                        run_id=run_id,
                    )
                )
        final_path = run_dir / "final_submission.csv"
        rows = columns = None
        if exit_code == 0 and final_path.exists():
            validation = evaluate_final_csv(final_path, authoritative_records)
            if any(
                item.blocking and item.status.value != "pass" for item in validation
            ):
                exit_code = 1
            with final_path.open(encoding="utf-8", newline="") as handle:
                parsed = list(csv.reader(handle))
            rows = max(0, len(parsed) - 1)
            columns = len(parsed[0]) if parsed else 0
        runs.append(
            ReproducibilityRun(
                run_id=run_id,
                exit_code=exit_code,
                duration_ms=round((perf_counter() - started) * 1000),
                timed_out=timed_out,
                artifacts=tuple(artifacts),
                final_csv_rows=rows,
                final_csv_columns=columns,
                stdout_tail=stdout,
                stderr_tail=stderr,
            )
        )
    comparisons = tuple(
        _compare_artifact(name, runs, output_root) for name in CANONICAL_ARTIFACTS
    )
    reproducible = (
        run_count == 3
        and all(run.exit_code == 0 for run in runs)
        and all(item.identical for item in comparisons)
    )
    return ReproducibilityResult(
        formal=run_count == 3,
        run_count=run_count,
        runs=tuple(runs),
        comparisons=comparisons,
        overall_reproducible=reproducible,
    )


def _compare_artifact(
    name: str, runs: Sequence[ReproducibilityRun], root: Path
) -> ArtifactComparison:
    found = []
    for run in runs:
        item = next(
            (
                artifact
                for artifact in run.artifacts
                if Path(artifact.relative_path).name == name
            ),
            None,
        )
        if item is not None:
            found.append(item)
    identical = (
        len(found) == len(runs)
        and len({item.sha256 for item in found}) == 1
        and len({item.byte_size for item in found}) == 1
    )
    first_difference = None
    if len(found) >= 2 and not identical:
        paths = [root / item.relative_path for item in found]
        first_difference = _first_difference(
            paths[0].read_bytes(), paths[1].read_bytes()
        )
    return ArtifactComparison(
        artifact_name=name,
        identical=identical,
        hashes=tuple(item.sha256 for item in found),
        byte_sizes=tuple(item.byte_size for item in found),
        first_difference=first_difference,
    )


def _first_difference(left: bytes, right: bytes) -> str:
    limit = min(len(left), len(right))
    offset = next(
        (index for index in range(limit) if left[index] != right[index]), limit
    )
    return f"first differing byte offset {offset}; sizes {len(left)} and {len(right)}"
