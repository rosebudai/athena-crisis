"""Theme configuration loading and validation."""

import json
import os
from dataclasses import dataclass
from typing import Dict


THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")
REQUIRED_FIELDS = ["name", "prompt", "palette"]


class ValidationError(Exception):
    pass


@dataclass
class ThemeConfig:
    name: str
    description: str
    prompt: str
    palette: Dict[str, str]


def load_theme(path_or_name: str) -> ThemeConfig:
    """Load a theme from a JSON file path or by name from themes/ directory."""
    if os.path.isfile(path_or_name):
        path = path_or_name
    else:
        path = os.path.join(THEMES_DIR, f"{path_or_name}.json")

    if not os.path.exists(path):
        raise FileNotFoundError(f"Theme file not found: {path}")

    with open(path) as f:
        data = json.load(f)

    for field in REQUIRED_FIELDS:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    return ThemeConfig(
        name=data["name"],
        description=data.get("description", ""),
        prompt=data["prompt"],
        palette=data["palette"],
    )
