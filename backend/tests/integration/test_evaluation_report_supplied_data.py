import json
from pathlib import Path

from backend.app.domain.evaluation import EvaluationReport


def test_generated_formal_report_validates_when_present() -> None:
    path = Path("backend/data/output/evaluation/evaluation_report.json")
    if not path.exists():
        return
    report = EvaluationReport.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert report.run_count == 3
    assert report.overall_status == "pass"
