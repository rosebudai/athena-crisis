"""Progress and runtime manifests for sprite reskin runs."""

import json
import os
from datetime import datetime, timezone
from typing import Optional


def load_runtime_manifest(path: str) -> dict:
    if not os.path.exists(path):
        return {}

    with open(path) as f:
        return json.load(f)


def write_runtime_manifest(
    path: str,
    theme_name: str,
    sprite_names: list[str],
    direct_sprites: Optional[dict[str, str]] = None,
) -> dict:
    """Merge sprite overrides into the served runtime manifest.

    Existing tile overrides are preserved. The sprite override set is replaced
    for the active theme, which keeps the runtime manifest deterministic.
    """
    manifest = load_runtime_manifest(path)
    manifest["basePath"] = f"reskin/{theme_name}"
    manifest["sprites"] = sorted(dict.fromkeys(sprite_names))

    if direct_sprites:
        manifest["directSprites"] = {
            name: direct_sprites[name]
            for name in sorted(direct_sprites)
        }
    else:
        manifest.pop("directSprites", None)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    return manifest


class Manifest:
    def __init__(self, path: str, theme: str, source: str, provider: str):
        self.path = path
        self.data = {
            "theme": theme,
            "source": source,
            "provider": provider,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "assets": {},
        }

    @classmethod
    def load(cls, path: str) -> "Manifest":
        """Load an existing manifest from disk."""
        with open(path) as f:
            data = json.load(f)
        m = cls.__new__(cls)
        m.path = path
        m.data = data
        return m

    def save(self):
        """Flush manifest to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def is_completed(self, name: str, source_hash: str) -> bool:
        """Check if an asset was already processed with the same fingerprint."""
        entry = self.data["assets"].get(name)
        if entry is None:
            return False
        fingerprint = entry.get("fingerprint", entry.get("source_hash"))
        return entry.get("status") == "completed" and fingerprint == source_hash

    def get_status(self, name: str) -> Optional[dict]:
        return self.data["assets"].get(name)

    def mark_completed(
        self,
        name: str,
        source_hash: str,
        output_path: str,
        metadata: Optional[dict] = None,
    ):
        entry = {
            "status": "completed",
            "fingerprint": source_hash,
            "source_hash": source_hash,
            "output_path": output_path,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            entry["metadata"] = metadata
        self.data["assets"][name] = entry
        self.save()

    def mark_failed(self, name: str, error: str):
        entry = self.data["assets"].get(name, {})
        attempts = entry.get("attempts", 0) + 1
        self.data["assets"][name] = {
            "status": "failed",
            "error": error,
            "attempts": attempts,
        }
        self.save()

    def summary(self) -> dict:
        assets = self.data["assets"]
        return {
            "completed": sum(1 for a in assets.values() if a["status"] == "completed"),
            "failed": sum(1 for a in assets.values() if a["status"] == "failed"),
            "total": len(assets),
        }

    def completed_assets(self) -> dict[str, dict]:
        return {
            name: asset
            for name, asset in self.data["assets"].items()
            if asset.get("status") == "completed"
        }
