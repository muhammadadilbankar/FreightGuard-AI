"""Content-addressed validated plan cache for replay and live planning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...domain.assistant import AssistantConversationContext, AssistantQueryPlan


def plan_cache_key(
    question: str,
    context: AssistantConversationContext | None,
    snapshot_id: str,
    planner_version: str,
    policy_version: str,
    provider_identity: str,
) -> str:
    payload = {
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "context": context.model_dump(mode="json") if context else None,
        "snapshot_id": snapshot_id,
        "planner_version": planner_version,
        "policy_version": policy_version,
        "provider_identity": provider_identity,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_cached_plan(path: Path, key: str) -> AssistantQueryPlan | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
            plan_payload = entry["plan"]
            canonical = json.dumps(plan_payload, sort_keys=True, separators=(",", ":"))
            integrity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if entry.get("key") == key and entry.get("integrity_sha256") == integrity:
                return AssistantQueryPlan.model_validate(plan_payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def store_cached_plan(path: Path, key: str, plan: AssistantQueryPlan) -> None:
    payload = plan.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    entry = {
        "key": key,
        "plan": payload,
        "integrity_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
