import json
import os
import pytest

from utils.reskin.manifest import Manifest


@pytest.fixture
def manifest_path(tmp_path):
    return str(tmp_path / "manifest.json")


def test_new_manifest_creates_file(manifest_path):
    m = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m.save()
    assert os.path.exists(manifest_path)


def test_manifest_mark_completed(manifest_path):
    m = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m.mark_completed("Units-Infantry", source_hash="abc123", output_path="/out/Units-Infantry.png")
    assert m.is_completed("Units-Infantry", source_hash="abc123")


def test_manifest_completed_wrong_hash(manifest_path):
    m = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m.mark_completed("Units-Infantry", source_hash="abc123", output_path="/out/Units-Infantry.png")
    assert not m.is_completed("Units-Infantry", source_hash="different")


def test_manifest_mark_failed(manifest_path):
    m = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m.mark_failed("Units-Infantry", error="API timeout")
    status = m.get_status("Units-Infantry")
    assert status["status"] == "failed"
    assert status["error"] == "API timeout"


def test_manifest_load_existing(manifest_path):
    m1 = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m1.mark_completed("Units-Infantry", source_hash="abc123", output_path="/out/Units-Infantry.png")
    m1.save()

    m2 = Manifest.load(manifest_path)
    assert m2.is_completed("Units-Infantry", source_hash="abc123")


def test_manifest_summary(manifest_path):
    m = Manifest(manifest_path, theme="cyberpunk", source="athena-crisis", provider="echo")
    m.mark_completed("a.png", source_hash="h1", output_path="/out/a.png")
    m.mark_completed("b.png", source_hash="h2", output_path="/out/b.png")
    m.mark_failed("c.png", error="timeout")
    summary = m.summary()
    assert summary["completed"] == 2
    assert summary["failed"] == 1
    assert summary["total"] == 3
