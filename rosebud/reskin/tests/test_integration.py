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
def test_standard_dry_run_preserves_progress_with_force(tmp_path):
    """Run the standard one-sheet pipeline and verify `--force` keeps progress.

    This test exercises the real download path -- sprite source images are
    fetched from art.athenacrisis.com. A generous timeout is used since
    network speed varies.
    """
    output_dir = str(tmp_path / "output")

    first = subprocess.run(
        [
            sys.executable, RESKIN_SCRIPT,
            "--theme", "cyberpunk",
            "--dry-run",
            "--name", "Units-Infantry",
            "--output-dir", output_dir,
            "--repo-root", REPO_ROOT,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert first.returncode == 0, (
        f"CLI exited with code {first.returncode}\n"
        f"STDOUT:\n{first.stdout}\n"
        f"STDERR:\n{first.stderr}"
    )

    second = subprocess.run(
        [
            sys.executable, RESKIN_SCRIPT,
            "--theme", "cyberpunk",
            "--dry-run",
            "--name", "Units-HeavyTank",
            "--force",
            "--output-dir", output_dir,
            "--repo-root", REPO_ROOT,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert second.returncode == 0, (
        f"CLI exited with code {second.returncode}\n"
        f"STDOUT:\n{second.stdout}\n"
        f"STDERR:\n{second.stderr}"
    )

    theme_dir = os.path.join(output_dir, "cyberpunk")
    assert os.path.isfile(os.path.join(theme_dir, "Units-Infantry.png"))
    assert os.path.isfile(os.path.join(theme_dir, "Units-HeavyTank.png"))
    assert not os.path.exists(os.path.join(theme_dir, "grids"))

    runtime_manifest_path = os.path.join(output_dir, "manifest.json")
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
    assert runtime_manifest["sprites"] == [
        "Units-HeavyTank",
        "Units-Infantry",
    ], runtime_manifest["sprites"]
    assert "directSprites" not in runtime_manifest

    progress_manifest_path = os.path.join(theme_dir, ".progress.json")
    with open(progress_manifest_path) as f:
        progress_manifest = json.load(f)
    assert sorted(progress_manifest["assets"]) == [
        "Units-HeavyTank",
        "Units-Infantry",
    ]


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
