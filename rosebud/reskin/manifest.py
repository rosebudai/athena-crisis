"""Progress tracking manifest for resumable reskin runs."""

import json
import os
from datetime import datetime, timezone
from typing import Optional


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
        """Check if an asset was already processed with the same source hash."""
        entry = self.data["assets"].get(name)
        if entry is None:
            return False
        return entry.get("status") == "completed" and entry.get("source_hash") == source_hash

    def get_status(self, name: str) -> Optional[dict]:
        return self.data["assets"].get(name)

    def mark_completed(self, name: str, source_hash: str, output_path: str):
        self.data["assets"][name] = {
            "status": "completed",
            "source_hash": source_hash,
            "output_path": output_path,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
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
