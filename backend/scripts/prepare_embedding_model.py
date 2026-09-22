"""Explicitly prepare the pinned Phase 7 embedding model for offline use."""

import json
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.core.logging import configure_logging

_METADATA_FILENAME = "freightguard_model_revision.json"


def main(settings: Settings | None = None) -> int:
    """Download the configured revision once and save a local reusable copy."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    destination = active_settings.embedding_model_path
    print("FreightGuard embedding-model preparation")
    if destination is None:
        print("Result: FAIL: EMBEDDING_MODEL_PATH must be configured.")
        return 1

    metadata_path = destination / _METADATA_FILENAME
    expected = {
        "model_name": active_settings.embedding_model_name,
        "revision": active_settings.embedding_model_revision,
    }
    try:
        if (destination / "config.json").is_file() and metadata_path.is_file():
            actual = json.loads(metadata_path.read_text(encoding="utf-8"))
            if actual != expected:
                print(
                    "Result: FAIL: existing local model metadata does not match "
                    "the configured name and revision."
                )
                return 1
            status = "already prepared"
        else:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(
                active_settings.embedding_model_name,
                revision=active_settings.embedding_model_revision,
                local_files_only=False,
                trust_remote_code=False,
                device="cpu",
            )
            model.eval()
            destination.mkdir(parents=True, exist_ok=True)
            model.save(str(destination))
            metadata_path.write_text(
                json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            status = "prepared"
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        print(f"Result: FAIL: unable to prepare embedding model: {exc}")
        return 1

    try:
        display_path = destination.relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = Path(destination)
    print(f"Model: {active_settings.embedding_model_name}")
    print(f"Revision: {active_settings.embedding_model_revision}")
    print(f"Local path: {display_path.as_posix()}")
    print(f"Result: PASS ({status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
