import json
from pathlib import Path


def test_generated_manifest_has_three_identical_final_hashes_when_present() -> None:
    path = Path("backend/data/output/evaluation/reproducibility_manifest.json")
    if not path.exists():
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["formal_run_count"] == 3
    comparison = next(
        item
        for item in manifest["canonical_artifact_comparisons"]
        if item["artifact_name"] == "final_submission.csv"
    )
    assert comparison["identical"] is True
    assert len(set(comparison["hashes"])) == 1
    audit = next(
        item
        for item in manifest["canonical_artifact_comparisons"]
        if item["artifact_name"] == "explanation_generation_audit.jsonl"
    )
    assert audit["identical"] is True
    assert len(set(audit["hashes"])) == 1
