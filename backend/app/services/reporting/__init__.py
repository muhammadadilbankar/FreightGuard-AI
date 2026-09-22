"""Public reporting services for deterministic generated artifacts."""

from .candidate_csv import (
    CANDIDATE_OUTPUT_FILENAME,
    PEER_UNAVAILABLE_TEXT,
    PRELIMINARY_REASON,
    build_candidate_output,
    candidate_csv_sha256,
    validate_candidate_csv,
    write_candidate_csv,
)
from .errors import (
    CompiledNotesSerializationError,
    EvidenceAuditError,
    EvidenceOutputContractError,
    ExplanationAuditError,
    FinalSubmissionError,
    OutputContractError,
    ReportingError,
)
from .explanation_audit import (
    EXPLANATION_AUDIT_FILENAME,
    build_explanation_audits,
    explanation_audit_sha256,
    read_explanation_audit_jsonl,
    validate_explanation_audit_jsonl,
    write_explanation_audit_jsonl,
)
from .final_submission import (
    FINAL_SUBMISSION_FILENAME,
    build_final_submission,
    validate_final_submission_csv,
    write_final_submission,
)
from .evidence_audit import (
    EVIDENCE_AUDIT_FILENAME,
    evidence_audit_sha256,
    read_evidence_audit_jsonl,
    validate_evidence_audit_jsonl,
    write_evidence_audit_jsonl,
)
from .evidence_csv import (
    EVIDENCE_REVIEWED_FILENAME,
    build_evidence_reviewed_output,
    validate_evidence_reviewed_csv,
    write_evidence_reviewed_csv,
)

__all__ = [
    "CANDIDATE_OUTPUT_FILENAME",
    "CompiledNotesSerializationError",
    "EVIDENCE_AUDIT_FILENAME",
    "EVIDENCE_REVIEWED_FILENAME",
    "EXPLANATION_AUDIT_FILENAME",
    "FINAL_SUBMISSION_FILENAME",
    "EvidenceAuditError",
    "EvidenceOutputContractError",
    "ExplanationAuditError",
    "FinalSubmissionError",
    "OutputContractError",
    "PEER_UNAVAILABLE_TEXT",
    "PRELIMINARY_REASON",
    "ReportingError",
    "build_candidate_output",
    "candidate_csv_sha256",
    "build_evidence_reviewed_output",
    "build_explanation_audits",
    "build_final_submission",
    "evidence_audit_sha256",
    "explanation_audit_sha256",
    "read_explanation_audit_jsonl",
    "read_evidence_audit_jsonl",
    "validate_candidate_csv",
    "validate_evidence_audit_jsonl",
    "validate_evidence_reviewed_csv",
    "validate_explanation_audit_jsonl",
    "validate_final_submission_csv",
    "write_candidate_csv",
    "write_evidence_audit_jsonl",
    "write_evidence_reviewed_csv",
    "write_explanation_audit_jsonl",
    "write_final_submission",
]
