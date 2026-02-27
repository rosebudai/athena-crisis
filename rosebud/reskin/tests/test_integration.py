"""End-to-end integration tests for the reskin pipeline.

Runs the full reskin CLI as a subprocess with the echo provider (dry-run)
and verifies the outputs match expectations.
"""

import json
import os
import subprocess
import sys

import pytest

# Ensure utils/ is on sys.path so reskin subpackage imports work.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

RESKIN_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "reskin.py")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")


@pytest.mark.slow
def test_batch_dry_run(tmp_path):
    """Run the full batch pipeline with echo provider and verify outputs.

    This test exercises the real download path -- sprite source images are
    fetched from art.athenacrisis.com.  A generous timeout is used since
    network speed varies.
    """
    output_dir = str(tmp_path / "output")

    result = subprocess.run(
        [
            sys.executable, RESKIN_SCRIPT,
            "--theme", "cyberpunk",
            "--batch",
            "--dry-run",
            "--output-dir", output_dir,
            "--repo-root", REPO_ROOT,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # ---- Exit code ----
    assert result.returncode == 0, (
        f"CLI exited with code {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # ---- Grid directory exists ----
    grids_dir = os.path.join(output_dir, "cyberpunk", "grids")
    assert os.path.isdir(grids_dir), f"Grid directory missing: {grids_dir}"

    # ---- Grid manifest exists and is valid ----
    grid_manifest_path = os.path.join(grids_dir, "manifest.json")
    assert os.path.isfile(grid_manifest_path), (
        f"Grid manifest missing: {grid_manifest_path}"
    )

    with open(grid_manifest_path) as f:
        grid_manifest = json.load(f)

    assert "batches" in grid_manifest
    assert len(grid_manifest["batches"]) >= 1, (
        f"Expected at least 1 batch, got {len(grid_manifest['batches'])}"
    )

    # ---- Individual sprite PNGs exist ----
    theme_dir = os.path.join(output_dir, "cyberpunk")
    png_files = [
        f for f in os.listdir(theme_dir)
        if f.endswith(".png")
    ]
    assert len(png_files) > 0, (
        f"No sprite PNGs found in {theme_dir}. "
        f"Contents: {os.listdir(theme_dir)}"
    )

    # ---- Runtime manifest exists and is valid ----
    runtime_manifest_path = os.path.join(theme_dir, "manifest.json")
    assert os.path.isfile(runtime_manifest_path), (
        f"Runtime manifest missing: {runtime_manifest_path}"
    )

    with open(runtime_manifest_path) as f:
        runtime_manifest = json.load(f)

    assert "basePath" in runtime_manifest, (
        "Runtime manifest missing 'basePath'"
    )
    assert "sprites" in runtime_manifest, (
        "Runtime manifest missing 'sprites'"
    )
    assert len(runtime_manifest["sprites"]) > 0, (
        "Runtime manifest 'sprites' array is empty"
    )

    # ---- At least 70 sprites extracted ----
    sprite_count = len(runtime_manifest["sprites"])
    assert sprite_count >= 70, (
        f"Expected at least 70 sprites, got {sprite_count}"
    )


def test_full_suite_passes():
    """Verify all unit tests pass."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "rosebud/reskin/tests/", "-v",
            "--ignore=rosebud/reskin/tests/test_integration.py",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Tests failed:\n{result.stdout}\n{result.stderr}"
    )
