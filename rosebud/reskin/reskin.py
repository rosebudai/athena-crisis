#!/usr/bin/env python3
"""Reskin pipeline CLI -- reskin Athena Crisis assets into themed styles."""

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
from manifest import Manifest
from providers.echo import EchoProvider
from providers.base import ReskinProvider
from transforms.ai_reskin import ai_reskin
from transforms.palette_swap import palette_swap

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
MAX_RETRIES = 3


def get_provider(name: str) -> ReskinProvider:
    """Instantiate a provider by name."""
    if name == "echo":
        return EchoProvider()
    if name == "fal_gemini":
        from providers.fal_gemini import FalGeminiProvider
        return FalGeminiProvider()
    raise ValueError(f"Unknown provider: {name}")


def file_hash(path: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def process_asset(asset, theme, provider, output_dir, palette_only=False):
    """Process a single asset through the appropriate transform.

    Returns output_path on success, raises on failure.
    """
    if asset.category in ("shadow", "decorator") or palette_only:
        image_bytes = palette_swap(asset.source_path, theme.palette)
    else:
        image_bytes = ai_reskin(
            asset.source_path, asset.category, theme.prompt, provider
        )

    # Post-process: resize AI output to match original dimensions and
    # restore alpha channel.  AI models often output 4096x4096 RGB images
    # regardless of the input size.
    from PIL import Image
    import io

    original = Image.open(asset.source_path).convert("RGBA")
    result = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    if result.size != original.size:
        result = result.resize(original.size, Image.LANCZOS)

    # Restore alpha from original (AI destroys transparency)
    r, g, b, _ = result.split()
    _, _, _, a = original.split()
    result = Image.merge("RGBA", (r, g, b, a))

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    # Write output as PNG under output_dir/theme.name/
    output_path = os.path.join(output_dir, theme.name, f"{asset.name}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    return output_path


def run_batch(args, theme, provider):
    """Batch mode: group assets into 4x4 grids and restyle via AI.

    Steps:
      1. Discover assets
      2. Build 4x4 grid images (16 sprites each)
      3. Send each grid to AI provider
      4. Extract restyled sprites, restore alpha masks, save individually
      5. Write runtime manifest for Sprites.tsx integration
    """
    from transforms.grid_batch import (
        build_grids,
        build_grid_prompt,
        extract_and_save,
    )

    assets = discover_assets(
        args.repo_root, category=args.category
    )
    print(f"Discovered {len(assets)} assets")
    if not assets:
        print("No assets found. Check category filter.")
        sys.exit(1)

    theme_output = os.path.join(args.output_dir, theme.name)
    grids_dir = os.path.join(theme_output, "grids")
    restyled_dir = os.path.join(theme_output, "restyled")
    sprites_dir = os.path.join(theme_output)

    # Step 1: Build grids
    print("\n=== Building grids ===")
    grid_manifest = build_grids(assets, grids_dir)

    # Step 2: Send each grid to AI provider
    print("\n=== Restyling grids via AI ===")
    os.makedirs(restyled_dir, exist_ok=True)
    total_batches = len(grid_manifest["batches"])

    for i, batch_meta in enumerate(grid_manifest["batches"], 1):
        batch_id = batch_meta["batch_id"]
        grid_path = batch_meta["grid_file"]
        output_path = os.path.join(restyled_dir, f"{batch_id}_restyled.png")

        if not args.force and os.path.exists(output_path):
            print(f"[{i}/{total_batches}] {batch_id}: skipping (exists)")
            continue

        n_sprites = len(batch_meta["sprites"])
        print(
            f"[{i}/{total_batches}] {batch_id}: "
            f"{n_sprites} sprites...",
            end=" ",
            flush=True,
        )

        prompt = build_grid_prompt(batch_meta, theme.prompt)

        # Save prompt for debugging
        prompt_path = os.path.join(restyled_dir, f"{batch_id}_prompt.txt")
        with open(prompt_path, "w") as f:
            f.write(prompt)

        ok = provider.transform_grid(grid_path, prompt, output_path)
        print("OK" if ok else "FAILED")

    # Step 3: Extract individual sprites
    print("\n=== Extracting sprites ===")
    results = extract_and_save(
        grid_manifest, restyled_dir, sprites_dir
    )

    # Step 4: Write runtime manifest for Sprites.tsx integration
    runtime_manifest = {
        "basePath": f"reskin/{theme.name}",
        "sprites": [name for name, _ in results],
    }
    runtime_manifest_path = os.path.join(sprites_dir, "manifest.json")
    os.makedirs(os.path.dirname(runtime_manifest_path), exist_ok=True)
    with open(runtime_manifest_path, "w") as f:
        json.dump(runtime_manifest, f, indent=2)

    print(f"\n--- Summary ---")
    print(f"Grids:     {total_batches}")
    print(f"Extracted: {len(results)}")
    print(f"Output:    {sprites_dir}")
    print(f"Manifest:  {runtime_manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Reskin Athena Crisis assets into themed styles."
    )
    parser.add_argument(
        "--theme", required=True,
        help="Theme name or path to theme JSON",
    )
    parser.add_argument(
        "--category",
        choices=["unit-sprite", "building", "portrait", "icon", "effect"],
        help="Process only this category",
    )
    parser.add_argument(
        "--provider", default="echo",
        help="AI provider name (default: echo)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use echo provider (no API calls)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all assets, ignore manifest",
    )
    parser.add_argument(
        "--palette-only", action="store_true",
        help="Use palette swap for all categories (skip AI provider)",
    )
    parser.add_argument(
        "--batch", action="store_true",
        help="Use grid batching (4x4 grids, 16x fewer API calls)",
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help="Output directory",
    )
    parser.add_argument(
        "--repo-root",
        default=os.path.join(os.path.dirname(__file__), "..", ".."),
        help="Path to athena-crisis repo root",
    )

    args = parser.parse_args()

    # Load theme
    theme = load_theme(args.theme)
    print(f"Theme: {theme.name} -- {theme.description}")

    # Get provider (palette-only mode doesn't need a real provider)
    if args.dry_run or args.palette_only:
        provider = EchoProvider()
        provider_name = "echo"
    else:
        provider = get_provider(args.provider)
        provider_name = args.provider

    # Batch mode: grid-based AI restyling
    if args.batch:
        run_batch(args, theme, provider)
        return

    # Standard mode: process assets one at a time
    assets = discover_assets(args.repo_root, category=args.category)
    print(f"Discovered {len(assets)} assets")

    if not assets:
        print("No assets found. Check category filter.")
        sys.exit(1)

    # Load or create manifest
    manifest_dir = os.path.join(args.output_dir, theme.name)
    manifest_path = os.path.join(manifest_dir, "manifest.json")

    if os.path.exists(manifest_path) and not args.force:
        manifest = Manifest.load(manifest_path)
    else:
        manifest = Manifest(
            manifest_path, theme=theme.name,
            source="athena-crisis", provider=provider_name,
        )

    # Process assets
    completed = 0
    failed = 0
    skipped = 0

    for i, asset in enumerate(assets, 1):
        source_hash = file_hash(asset.source_path)

        # Check manifest for already-completed assets
        if not args.force and manifest.is_completed(asset.name, source_hash):
            skipped += 1
            continue

        print(
            f"[{i}/{len(assets)}] {asset.name} ({asset.category})...",
            end=" ", flush=True,
        )

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                output_path = process_asset(
                    asset, theme, provider, args.output_dir,
                    palette_only=args.palette_only,
                )
                manifest.mark_completed(asset.name, source_hash, output_path)
                completed += 1
                print("OK")
                break
            except NotImplementedError as e:
                # Provider not yet implemented
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

    # Summary
    print(f"\n--- Summary ---")
    print(f"Completed: {completed}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")
    print(f"Total:     {len(assets)}")
    print(f"Output:    {os.path.join(args.output_dir, theme.name)}")


if __name__ == "__main__":
    main()
