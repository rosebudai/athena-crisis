#!/usr/bin/env python3
"""Reskin pipeline CLI for named unit and building sprite sheets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# Ensure rosebud/reskin is on the path when run directly as a script.
# Also add the repo root so that submodule package imports work
# (e.g., echo.py's "from rosebud.reskin.providers.base import ...").
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from config import load_theme
from discovery import discover_assets
from manifest import Manifest, write_runtime_manifest
from providers.base import ReskinProvider
from providers.echo import EchoProvider
from providers.nano_banana import NanoBananaProvider
from transforms.ai_reskin import PROMPT_VERSION, ai_reskin
from transforms.palette_swap import palette_swap

DEFAULT_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "public", "reskin")
)
DEFAULT_CATEGORIES = ("unit-sprite", "building")
DIRECT_RUNTIME_SPRITES = {"Structures"}
MAX_RETRIES = 3


def get_provider(name: str) -> ReskinProvider:
    """Instantiate a provider by name."""
    if name == "echo":
        return EchoProvider()
    if name == "nano_banana":
        return NanoBananaProvider()
    raise ValueError(f"Unknown provider: {name}")


def file_hash(path: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def hash_json(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]


def resolve_categories(category_args: list[str] | None) -> list[str]:
    if category_args:
        return category_args
    return list(DEFAULT_CATEGORIES)


def build_asset_fingerprint(
    asset,
    *,
    theme,
    provider_name: str,
    provider_params: dict,
    style_reference_paths: list[str],
    palette_only: bool,
) -> tuple[str, dict]:
    style_reference_hashes = {
        os.path.basename(path): file_hash(path)
        for path in style_reference_paths
    }
    metadata = {
        "asset_name": asset.name,
        "category": asset.category,
        "source_hash": file_hash(asset.source_path),
        "style_reference_hashes": style_reference_hashes,
        "theme_name": theme.name,
        "theme_prompt": theme.prompt,
        "prompt_version": PROMPT_VERSION,
        "provider": provider_name,
        "provider_params": provider_params,
        "palette_only": palette_only,
    }
    return hash_json(metadata), metadata


def manifest_entries_for_assets(
    asset_names: list[str],
    theme_name: str,
) -> tuple[list[str], dict[str, str]]:
    sprite_names: list[str] = []
    direct_sprites: dict[str, str] = {}

    for name in sorted(dict.fromkeys(asset_names)):
        if name in DIRECT_RUNTIME_SPRITES:
            direct_sprites[name] = f"reskin/{theme_name}/{name}.png"
        else:
            sprite_names.append(name)

    return sprite_names, direct_sprites


def write_runtime_manifest_for_completed_assets(
    manifest: Manifest,
    output_dir: str,
    theme_name: str,
) -> str:
    completed_names = [
        name
        for name, entry in manifest.completed_assets().items()
        if os.path.exists(entry.get("output_path", ""))
    ]
    sprite_names, direct_sprites = manifest_entries_for_assets(
        completed_names, theme_name
    )
    runtime_manifest_path = os.path.join(output_dir, "manifest.json")
    write_runtime_manifest(
        runtime_manifest_path,
        theme_name,
        sprite_names,
        direct_sprites=direct_sprites,
    )
    return runtime_manifest_path


def process_asset(
    asset,
    theme,
    provider,
    output_dir,
    *,
    palette_only: bool = False,
    style_reference_paths: list[str] | None = None,
):
    """Process a single asset through the appropriate transform."""
    if asset.category in ("shadow", "decorator") or palette_only:
        image_bytes = palette_swap(asset.source_path, theme.palette)
    else:
        image_bytes = ai_reskin(
            asset.source_path,
            asset.category,
            theme.prompt,
            provider,
            asset_name=asset.name,
            reference_image_paths=style_reference_paths or [],
        )

    from PIL import Image
    import io

    original = Image.open(asset.source_path).convert("RGBA")
    result = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    if result.size != original.size:
        raise ValueError(
            f"Provider returned {result.size}, expected {original.size}"
        )

    # Restore alpha from original (AI destroys transparency)
    r, g, b, _ = result.split()
    _, _, _, a = original.split()
    result = Image.merge("RGBA", (r, g, b, a))

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    output_path = os.path.join(output_dir, theme.name, f"{asset.name}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path


def validate_style_reference_paths(paths: list[str]) -> list[str]:
    resolved_paths = [os.path.abspath(path) for path in paths]
    missing = [path for path in resolved_paths if not os.path.exists(path)]
    if missing:
        raise FileNotFoundError(
            "Style reference file(s) not found: " + ", ".join(missing)
        )
    return resolved_paths


def main():
    parser = argparse.ArgumentParser(
        description="Reskin Athena Crisis unit and building sprite sheets."
    )
    parser.add_argument(
        "--theme",
        required=True,
        help="Theme name or path to theme JSON",
    )
    parser.add_argument(
        "--category",
        action="append",
        choices=["unit-sprite", "building", "portrait", "icon", "effect"],
        help="Process only this category. Repeat to include multiple categories.",
    )
    parser.add_argument(
        "--name",
        help="Process only this sprite name (e.g. Units-HeavyTank)",
    )
    parser.add_argument(
        "--provider",
        default="nano_banana",
        choices=["nano_banana"],
        help="AI provider name (default: nano_banana)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use echo provider (no API calls)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all assets, ignore progress manifest",
    )
    parser.add_argument(
        "--palette-only",
        action="store_true",
        help="Debug/fallback mode: use palette swap instead of AI generation.",
    )
    parser.add_argument(
        "--style-reference",
        action="append",
        default=[],
        help="Optional style reference image path. Repeat for multiple images.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Served reskin output directory",
    )
    parser.add_argument(
        "--repo-root",
        default=os.path.join(os.path.dirname(__file__), "..", ".."),
        help="Path to athena-crisis repo root",
    )

    args = parser.parse_args()

    args.output_dir = os.path.abspath(args.output_dir)
    style_reference_paths = validate_style_reference_paths(args.style_reference)
    categories = resolve_categories(args.category)

    theme = load_theme(args.theme)
    print(f"Theme: {theme.name} -- {theme.description}")
    print(f"Categories: {', '.join(categories)}")

    if args.dry_run or args.palette_only:
        provider = EchoProvider()
        provider_name = "echo"
    else:
        provider = get_provider(args.provider)
        provider_name = args.provider

    requested_names = [args.name] if args.name else None
    assets = discover_assets(
        args.repo_root,
        category=categories,
        names=requested_names,
    )
    print(f"Discovered {len(assets)} assets")

    if not assets:
        print("No assets found. Check category/name filter.")
        sys.exit(1)

    theme_output_dir = os.path.join(args.output_dir, theme.name)
    progress_manifest_path = os.path.join(theme_output_dir, ".progress.json")

    if os.path.exists(progress_manifest_path):
        manifest = Manifest.load(progress_manifest_path)
    else:
        manifest = Manifest(
            progress_manifest_path,
            theme=theme.name,
            source="athena-crisis",
            provider=provider_name,
        )

    completed = 0
    failed = 0
    skipped = 0
    provider_params = {
        "style_reference_count": len(style_reference_paths),
    }

    for i, asset in enumerate(assets, 1):
        fingerprint, metadata = build_asset_fingerprint(
            asset,
            theme=theme,
            provider_name=provider_name,
            provider_params=provider_params,
            style_reference_paths=style_reference_paths,
            palette_only=args.palette_only,
        )

        if not args.force and manifest.is_completed(asset.name, fingerprint):
            skipped += 1
            continue

        print(
            f"[{i}/{len(assets)}] {asset.name} ({asset.category})...",
            end=" ",
            flush=True,
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                output_path = process_asset(
                    asset,
                    theme,
                    provider,
                    args.output_dir,
                    palette_only=args.palette_only,
                    style_reference_paths=style_reference_paths,
                )
                manifest.mark_completed(
                    asset.name,
                    source_hash=fingerprint,
                    output_path=output_path,
                    metadata=metadata,
                )
                completed += 1
                print("OK")
                break
            except NotImplementedError as e:
                manifest.mark_failed(asset.name, str(e))
                failed += 1
                print(f"SKIP ({e})")
                break
            except Exception as e:
                if attempt == MAX_RETRIES:
                    manifest.mark_failed(asset.name, str(e))
                    failed += 1
                    print(f"FAILED ({e})")
                else:
                    print(f"retry {attempt}...", end=" ", flush=True)

    runtime_manifest_path = write_runtime_manifest_for_completed_assets(
        manifest, args.output_dir, theme.name
    )

    print("\n--- Summary ---")
    print(f"Completed: {completed}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Total:     {len(assets)}")
    print(f"Output:    {theme_output_dir}")
    print(f"Progress:  {progress_manifest_path}")
    print(f"Manifest:  {runtime_manifest_path}")


if __name__ == "__main__":
    main()
