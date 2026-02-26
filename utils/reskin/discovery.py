"""Asset discovery for Athena Crisis sprite sheets.

Parses SpriteVariants.tsx to find all sprite variant names, downloads
source images from the Athena Crisis art server, and classifies them
by category (unit-sprite, building, portrait, icon, shadow, decorator, effect).

Note: The art server does not host raw source sheets (e.g. Units-Infantry.png).
Instead, only palette-swapped variants are available (e.g. Units-Infantry-0.png
for player 0).  We download the "-0" variant as the AI input — the pipeline
restyles the default-colored sprite, and the runtime palette-swap system
regenerates team colors from the reskinned output.
"""

import os
import re
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


ART_BASE_URL = "https://art.athenacrisis.com/v19"
SPRITE_VARIANTS_REL_PATH = os.path.join("athena", "info", "SpriteVariants.tsx")

# Classification rules: (prefix_or_name, category)
# Checked in order; first match wins.
_CLASSIFICATION_RULES = [
    # Exact-name matches first
    (("Buildings",), "building"),
    (("Building-Create",), "building"),
    (("Portraits",), "portrait"),
    (("Label", "Medal", "Message"), "icon"),
    (("BuildingsShadow", "StructuresShadow"), "shadow"),
    (("Decorators",), "decorator"),
]

# Prefix-based match
_PREFIX_RULES = [
    ("Units-", "unit-sprite"),
]


def _classify(name: str) -> str:
    """Return the category string for a given sprite variant name."""
    for names, category in _CLASSIFICATION_RULES:
        if name in names:
            return category

    for prefix, category in _PREFIX_RULES:
        if name.startswith(prefix):
            return category

    return "effect"


@dataclass
class AssetInfo:
    name: str
    source_path: str
    source_url: str
    category: str


def parse_sprite_variants(repo_root: str) -> List[str]:
    """Parse SpriteVariants.tsx and return a sorted list of sprite variant names."""
    path = os.path.join(repo_root, SPRITE_VARIANTS_REL_PATH)
    with open(path) as f:
        content = f.read()
    names = re.findall(r"'([^']+)'", content)
    return sorted(set(names))


def discover_assets(
    repo_root: str,
    category: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> List[AssetInfo]:
    """Discover Athena Crisis sprite assets and optionally download them.

    Args:
        repo_root: Path to the athena-crisis repo root.
        category: Optional category filter (e.g. "unit-sprite", "building").
        cache_dir: Directory to cache downloaded PNGs. Defaults to
                   ``output/.cache/`` relative to the reskin package.

    Returns:
        List of AssetInfo dataclass instances.
    """
    if cache_dir is None:
        cache_dir = os.path.join(os.path.dirname(__file__), "output", ".cache")

    os.makedirs(cache_dir, exist_ok=True)

    names = parse_sprite_variants(repo_root)
    total = len(names)
    assets: List[AssetInfo] = []

    for idx, name in enumerate(names, start=1):
        cat = _classify(name)
        if category is not None and cat != category:
            continue

        source_url = f"{ART_BASE_URL}/{name}-0.png"
        source_path = os.path.join(cache_dir, f"{name}.png")

        if not os.path.exists(source_path):
            print(f"[{idx}/{total}] Downloading {name}...")
            req = urllib.request.Request(
                source_url,
                headers={"User-Agent": "AthenaCrisis-Reskin/1.0"},
            )
            with urllib.request.urlopen(req) as resp, open(source_path, "wb") as out:
                out.write(resp.read())
        else:
            print(f"[{idx}/{total}] Cached {name}")

        assets.append(
            AssetInfo(
                name=name,
                source_path=source_path,
                source_url=source_url,
                category=cat,
            )
        )

    return assets
