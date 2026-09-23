"""Evaluation report wire contracts."""

from ...domain.evaluation import EvaluationReport
from .common import DataEnvelope, WireModel


class EvaluationReportData(WireModel):
    report: EvaluationReport
    report_sha256: str


EvaluationReportResponse = DataEnvelope[EvaluationReportData]
