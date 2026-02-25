#!/usr/bin/env python3
"""
Package the Athena Crisis Vite build output into a zip file compatible with
Rosebud's import_project_from_zip / import_project_from_local_zip commands.

Zip structure rules (matching _zip_import_utils.py):
  - Files under `assets/` top-level directory -> treated as binary assets
    (uploaded to GCS as MediaFile/Asset).
  - Everything else -> treated as UTF-8 text project files
    (stored as GenericFile records in DB, served via /api/server/{revisionId}/).

Since JS/CSS/HTML must be served as GenericFile text records, they must NOT be
placed under the `assets/` prefix in the zip. Only truly binary files (fonts,
images, audio) go under `assets/`.

Usage:
    python package-for-rosebud.py [--dist-dir DIR] [--output FILE]
"""

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

# Extensions considered binary -> placed under assets/ in the zip
BINARY_EXTENSIONS = frozenset({
    ".woff2", ".woff", ".ttf", ".otf", ".eot",   # fonts
    ".ogg", ".mp3", ".wav", ".flac", ".aac",      # audio
    ".png", ".jpg", ".jpeg", ".gif", ".webp",     # images
    ".svg", ".ico",                                 # icons/vector
    ".mp4", ".webm",                                # video
    ".glb", ".gltf",                                # 3D models
    ".bin",                                         # binary data
})


def is_binary_file(file_path: Path) -> bool:
    """Determine if a file should be treated as a binary asset."""
    return file_path.suffix.lower() in BINARY_EXTENSIONS


def rewrite_asset_paths(content: str, relocated_files: dict[str, str]) -> str:
    """
    Rewrite asset paths in HTML/JS/CSS content.

    When text files are relocated from assets/ to root, references to them
    (e.g., /assets/index-xxx.js) must be updated to their new paths (e.g., /index-xxx.js).

    Args:
        content: The file content to rewrite.
        relocated_files: Mapping of original relative paths to new zip paths.
                         e.g., {"assets/index-DpjBJGlC.js": "index-DpjBJGlC.js"}
    """
    result = content
    for original_rel, new_zip_path in relocated_files.items():
        # Replace both absolute (/assets/...) and relative (assets/...) references
        # Handle src="..." href="..." and url(...) patterns
        old_abs = f"/{original_rel}"
        new_abs = f"/{new_zip_path}"
        if old_abs != new_abs:
            result = result.replace(old_abs, new_abs)
        # Also handle relative references (without leading /)
        if original_rel != new_zip_path:
            result = result.replace(original_rel, new_zip_path)
    return result


def package_dist(dist_dir: Path, output_path: Path) -> None:
    """
    Walk dist_dir and create a zip with the correct structure for Rosebud import.

    Binary files -> assets/{filename}  (flat, under assets/ prefix)
    Text files   -> {relative_path}    (preserving directory structure, NO assets/ prefix)

    HTML files are rewritten so that references to relocated text files
    (JS/CSS moved out of assets/) point to their new paths.
    """
    if not dist_dir.is_dir():
        print(f"Error: dist directory does not exist: {dist_dir}", file=sys.stderr)
        sys.exit(1)

    text_files: list[tuple[Path, str]] = []   # (fs_path, zip_path)
    binary_files: list[tuple[Path, str]] = []  # (fs_path, zip_path)
    # Track text files that were relocated out of assets/ so we can rewrite refs
    relocated_files: dict[str, str] = {}  # original_rel_path -> new_zip_path

    for root, _dirs, files in os.walk(dist_dir):
        for filename in sorted(files):
            fs_path = Path(root) / filename
            rel_path = fs_path.relative_to(dist_dir)

            # Skip the output zip itself if it's inside the dist directory
            if fs_path.resolve() == output_path.resolve():
                continue

            if is_binary_file(fs_path):
                # Binary files go under assets/ with just their filename (flat)
                zip_path = f"assets/{filename}"
                binary_files.append((fs_path, zip_path))
            else:
                # Text files keep their relative path but must NOT start with assets/
                # If the Vite build put them under assets/, strip that prefix
                rel_str = str(rel_path)
                if rel_str.startswith("assets/") or rel_str.startswith("assets\\"):
                    # Move out of assets/ into a flat structure preserving just the filename
                    zip_path = rel_str.replace("assets/", "", 1).replace("assets\\", "", 1)
                    relocated_files[rel_str] = zip_path
                else:
                    zip_path = rel_str

                text_files.append((fs_path, zip_path))

    # Verify we have files to package
    total = len(text_files) + len(binary_files)
    if total == 0:
        print(f"Error: no files found in {dist_dir}", file=sys.stderr)
        sys.exit(1)

    if relocated_files:
        print("Relocated text files (out of assets/ prefix):")
        for orig, new in sorted(relocated_files.items()):
            print(f"  {orig} -> {new}")
        print()

    # Create the zip
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        print(f"Packaging {len(text_files)} text files and {len(binary_files)} binary files...")
        print()

        # File extensions that may contain references to relocated assets
        REWRITABLE_EXTENSIONS = frozenset({".html", ".htm", ".js", ".css", ".json"})

        print("Text files (-> GenericFile records):")
        for fs_path, zip_path in sorted(text_files, key=lambda x: x[1]):
            size = fs_path.stat().st_size

            # Rewrite asset references in text files that may contain paths
            if fs_path.suffix.lower() in REWRITABLE_EXTENSIONS and relocated_files:
                content = fs_path.read_text(encoding="utf-8")
                rewritten = rewrite_asset_paths(content, relocated_files)
                if rewritten != content:
                    print(f"  {zip_path:<50} ({len(rewritten):>10,} bytes) [paths rewritten]")
                    zf.writestr(zip_path, rewritten)
                else:
                    print(f"  {zip_path:<50} ({size:>10,} bytes)")
                    zf.write(fs_path, zip_path)
            else:
                print(f"  {zip_path:<50} ({size:>10,} bytes)")
                zf.write(fs_path, zip_path)

        print()
        print("Binary files (-> GCS assets):")
        for fs_path, zip_path in sorted(binary_files, key=lambda x: x[1]):
            size = fs_path.stat().st_size
            print(f"  {zip_path:<50} ({size:>10,} bytes)")
            zf.write(fs_path, zip_path)

    zip_size = output_path.stat().st_size
    print()
    print(f"Created: {output_path}")
    print(f"Zip size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)")
    print(f"Total entries: {total} ({len(text_files)} text, {len(binary_files)} binary)")


def main():
    parser = argparse.ArgumentParser(
        description="Package Athena Crisis build for Rosebud import"
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "dist",
        help="Path to Vite dist/ output directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output zip file path (default: dist/athena-crisis-rosebud.zip)",
    )
    args = parser.parse_args()

    dist_dir = args.dist_dir.resolve()
    output = args.output
    if output is None:
        output = dist_dir / "athena-crisis-rosebud.zip"
    output = output.resolve()

    print(f"Source: {dist_dir}")
    print(f"Output: {output}")
    print()

    package_dist(dist_dir, output)


if __name__ == "__main__":
    main()
