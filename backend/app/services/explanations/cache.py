"""Validated content-addressed JSONL explanation cache."""

from collections.abc import Iterable
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

from pydantic import ValidationError

from ...domain.explanations import (
    ExplanationCacheEntry,
    GeneratedExplanation,
    GroundedExplanationRequest,
    ProviderIdentity,
)
from .errors import ExplanationCacheError
from .prompts import canonical_request_json


def response_schema_fingerprint() -> str:
    canonical = json.dumps(
        GeneratedExplanation.model_json_schema(), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def request_sha256(request: GroundedExplanationRequest) -> str:
    return hashlib.sha256(canonical_request_json(request).encode("utf-8")).hexdigest()


def build_cache_key(
    request: GroundedExplanationRequest,
    identity: ProviderIdentity,
    *,
    schema_fingerprint: str | None = None,
) -> str:
    payload = {
        "schema_version": request.schema_version,
        "prompt_version": request.prompt_version,
        "provider": identity.model_dump(mode="json"),
        "request": json.loads(canonical_request_json(request)),
        "schema_fingerprint": schema_fingerprint or response_schema_fingerprint(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ExplanationCache:
    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled
        self._lock = RLock()
        self._entries: dict[str, ExplanationCacheEntry] | None = None

    def get(
        self, key: str, request: GroundedExplanationRequest, identity: ProviderIdentity
    ) -> ExplanationCacheEntry | None:
        if not self.enabled:
            return None
        with self._lock:
            entries = self._load()
            entry = entries.get(key)
            if entry is None:
                return None
            expected_schema = response_schema_fingerprint()
            if (
                entry.cache_key != build_cache_key(
                    request, identity, schema_fingerprint=expected_schema
                )
                or entry.request_sha256 != request_sha256(request)
                or entry.schema_fingerprint != expected_schema
                or entry.provider_identity != identity
                or entry.prompt_version != request.prompt_version
            ):
                raise ExplanationCacheError("Cache entry failed integrity validation.")
            return entry

    def put(self, entry: ExplanationCacheEntry) -> None:
        if not self.enabled:
            return
        with self._lock:
            entries = self._load()
            existing = entries.get(entry.cache_key)
            if existing is not None and existing != entry:
                raise ExplanationCacheError("Cache key already has different content.")
            entries[entry.cache_key] = entry
            self._write(entries.values())

    def _load(self) -> dict[str, ExplanationCacheEntry]:
        if self._entries is not None:
            return self._entries
        if not self.path.exists():
            self._entries = {}
            return self._entries
        try:
            raw = self.path.read_bytes()
            if raw and (not raw.endswith(b"\n") or raw.endswith(b"\n\n")):
                raise ExplanationCacheError("Cache must end with exactly one newline.")
            parsed = [
                ExplanationCacheEntry.model_validate(json.loads(line))
                for line in raw.decode("utf-8").splitlines()
            ]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ExplanationCacheError("Explanation cache is invalid.") from exc
        keys = [entry.cache_key for entry in parsed]
        if len(keys) != len(set(keys)):
            raise ExplanationCacheError("Explanation cache contains duplicate keys.")
        self._entries = {entry.cache_key: entry for entry in parsed}
        return self._entries

    def _write(self, entries: Iterable[ExplanationCacheEntry]) -> None:
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                delete=False,
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            ) as temporary:
                temporary_path = Path(temporary.name)
                for entry in sorted(entries, key=lambda item: item.cache_key):
                    temporary.write(
                        json.dumps(
                            entry.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
            os.replace(temporary_path, self.path)
        except OSError as exc:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
            raise ExplanationCacheError("Unable to update explanation cache.") from exc
