import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from reskin.transforms.ai_reskin import PROMPT_VERSION, ai_reskin, build_prompt


class StubProvider:
    def __init__(self):
        self.calls = []

    def transform(self, image_path, prompt, params):
        self.calls.append(
            {
                "image_path": image_path,
                "prompt": prompt,
                "params": params,
            }
        )
        return b"png"


def test_build_prompt_uses_v2_contract():
    prompt = build_prompt(
        "unit-sprite",
        "cozy brass clockwork",
        asset_name="Units-Infantry",
        reference_count=2,
    )

    assert PROMPT_VERSION in prompt
    assert "exact canvas dimensions" in prompt
    assert "Target asset name: Units-Infantry." in prompt
    assert "Additional reference image(s)" in prompt


def test_ai_reskin_passes_reference_images():
    provider = StubProvider()
    result = ai_reskin(
        "/tmp/source.png",
        "building",
        "warm stone fortress",
        provider,
        asset_name="Buildings",
        reference_image_paths=["/tmp/style-a.png", "/tmp/style-b.png"],
    )

    assert result == b"png"
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["image_path"] == "/tmp/source.png"
    assert call["params"]["reference_image_paths"] == [
        "/tmp/style-a.png",
        "/tmp/style-b.png",
    ]
    assert "Buildings" in call["prompt"]
