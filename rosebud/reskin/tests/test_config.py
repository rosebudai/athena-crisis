import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import pytest

from reskin.config import load_theme, ThemeConfig, ValidationError


@pytest.fixture
def cyberpunk_theme_data():
    return {
        "name": "cyberpunk",
        "description": "Neon-lit sci-fi warriors with glowing circuits and chrome armor",
        "prompt": "cyberpunk neon sci-fi style, glowing circuits, chrome metal, dark background",
        "palette": {
            "reds": "#ff0044",
            "browns": "#6600cc",
            "yellows": "#00ffff",
            "greens": "#00ff88",
        },
    }


@pytest.fixture
def theme_file(cyberpunk_theme_data, tmp_path):
    path = tmp_path / "cyberpunk.json"
    path.write_text(json.dumps(cyberpunk_theme_data))
    return str(path)


def test_load_theme_returns_theme_config(theme_file):
    theme = load_theme(theme_file)
    assert isinstance(theme, ThemeConfig)
    assert theme.name == "cyberpunk"
    assert theme.description == "Neon-lit sci-fi warriors with glowing circuits and chrome armor"
    assert theme.prompt == "cyberpunk neon sci-fi style, glowing circuits, chrome metal, dark background"
    assert theme.palette["reds"] == "#ff0044"
    assert theme.palette["browns"] == "#6600cc"


def test_load_theme_missing_file():
    with pytest.raises(FileNotFoundError):
        load_theme("/nonexistent/theme.json")


def test_load_theme_missing_required_field(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"name": "bad"}))
    with pytest.raises(ValidationError):
        load_theme(str(path))


def test_load_theme_by_name():
    """Load a theme by name from the themes/ directory."""
    theme = load_theme("cyberpunk")
    assert theme.name == "cyberpunk"
    assert theme.palette["greens"] == "#00ff88"
