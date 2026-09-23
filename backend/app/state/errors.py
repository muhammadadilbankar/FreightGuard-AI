"""Typed state and application service failures."""


class ApplicationError(Exception):
    code = "application_error"


class AnalysisNotReadyError(ApplicationError):
    code = "analysis_not_ready"


class AnalysisRunInProgressError(ApplicationError):
    code = "analysis_run_in_progress"


class UnsupportedExplanationModeError(ApplicationError):
    code = "unsupported_explanation_mode"


class AnalysisRunFailedError(ApplicationError):
    code = "analysis_run_failed"


class AnomalyNotFoundError(ApplicationError):
    code = "anomaly_not_found"


class RootCauseNotApplicableError(ApplicationError):
    code = "root_cause_not_applicable"


class RootCauseUnavailableError(ApplicationError):
    code = "root_cause_unavailable"


class RootCauseInvariantError(ApplicationError):
    code = "root_cause_invariant_failed"


class RouteNotFoundError(ApplicationError):
    code = "route_not_found"


class EvaluationNotAvailableError(ApplicationError):
    code = "evaluation_not_available"


class ExportNotAvailableError(ApplicationError):
    code = "export_not_available"


class InvalidQueryError(ApplicationError):
    code = "request_validation_failed"
