"""Fail-closed validation for deterministic assistant compositions."""

from ...domain.assistant import AssistantResponseData, FactRegistry
from .composition import OPERATIONAL_BOUNDARY


def validate_grounding(response: AssistantResponseData, registry: FactRegistry) -> None:
    fact_citations = {citation for fact in registry.facts for citation in fact.citation_ids}
    response_citations = {item.citation_id for item in response.citations}
    if not fact_citations <= response_citations:
        raise ValueError("Assistant citations and fact registry do not reconcile.")
    if any(not claim.citation_ids for claim in response.claims):
        raise ValueError("Every assistant claim must be cited.")
    if any(not set(claim.citation_ids) <= response_citations for claim in response.claims):
        raise ValueError("Assistant claim cites an unknown source.")
    operational = any(item.citation_type.value == "root_cause" for item in response.citations)
    if operational and not any(claim.text == OPERATIONAL_BOUNDARY for claim in response.claims):
        raise ValueError("Operational answers require the evidence boundary.")
    if any("has been cleared" in claim.text.casefold() for claim in response.claims):
        raise ValueError("Assistant response contains prohibited mutation language.")
