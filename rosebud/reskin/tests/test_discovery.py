import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from reskin.discovery import parse_sprite_variants, discover_assets, _classify, AssetInfo


REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")


def test_parse_sprite_variants_finds_names():
    names = parse_sprite_variants(REPO_ROOT)
    assert len(names) >= 80, f"Expected ~90 names, got {len(names)}"
    assert "Units-Infantry" in names
    assert "Buildings" in names
    assert "Portraits" in names


def test_classify_unit_sprite():
    assert _classify("Units-Infantry") == "unit-sprite"


def test_classify_building():
    assert _classify("Buildings") == "building"
    assert _classify("Building-Create") == "building"


def test_classify_portrait():
    assert _classify("Portraits") == "portrait"


def test_classify_icon():
    assert _classify("Label") == "icon"
    assert _classify("Medal") == "icon"
    assert _classify("Message") == "icon"


def test_classify_shadow():
    assert _classify("BuildingsShadow") == "shadow"
    assert _classify("StructuresShadow") == "shadow"


def test_classify_decorator():
    assert _classify("Decorators") == "decorator"


def test_classify_effect():
    assert _classify("Capture") == "effect"
    assert _classify("Rescue") == "effect"
    assert _classify("Spawn") == "effect"
    assert _classify("NavalExplosion") == "effect"
    assert _classify("AttackOctopus") == "effect"
    assert _classify("Rescuing") == "effect"


def test_category_filter(tmp_path):
    """Verify that category filter returns only matching assets."""
    cache_dir = str(tmp_path / "cache")

    # Use discover_assets with category filter — it will try to download,
    # so we create fake cached files to avoid network access.
    names = parse_sprite_variants(REPO_ROOT)
    os.makedirs(cache_dir, exist_ok=True)
    for name in names:
        # Create empty placeholder files so download is skipped
        open(os.path.join(cache_dir, f"{name}.png"), "w").close()

    assets = discover_assets(REPO_ROOT, category="building", cache_dir=cache_dir)
    assert len(assets) > 0
    for asset in assets:
        assert asset.category == "building"

    # Verify that unit-sprite filter excludes buildings
    unit_assets = discover_assets(REPO_ROOT, category="unit-sprite", cache_dir=cache_dir)
    assert len(unit_assets) > 0
    for asset in unit_assets:
        assert asset.category == "unit-sprite"
    unit_names = {a.name for a in unit_assets}
    assert "Buildings" not in unit_names


def test_multi_category_filter_includes_structures(tmp_path):
    cache_dir = str(tmp_path / "cache")
    names = parse_sprite_variants(REPO_ROOT)
    os.makedirs(cache_dir, exist_ok=True)
    for name in names:
        open(os.path.join(cache_dir, f"{name}.png"), "w").close()
    open(os.path.join(cache_dir, "Structures.png"), "w").close()

    assets = discover_assets(
        REPO_ROOT,
        category=["unit-sprite", "building"],
        cache_dir=cache_dir,
    )

    asset_names = {asset.name for asset in assets}
    assert "Units-Infantry" in asset_names
    assert "Buildings" in asset_names
    assert "Structures" in asset_names
    assert "Portraits" not in asset_names


def test_name_filter_avoids_full_catalog_downloads(tmp_path):
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir, exist_ok=True)
    open(os.path.join(cache_dir, "Units-Infantry.png"), "w").close()

    assets = discover_assets(
        REPO_ROOT,
        category="unit-sprite",
        names=["Units-Infantry"],
        cache_dir=cache_dir,
    )

    assert [asset.name for asset in assets] == ["Units-Infantry"]
