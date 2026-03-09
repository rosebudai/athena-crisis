"""Focused tests for the new tile pipeline CLI and orchestration."""

from pathlib import Path

from rosebud.reskin.tile_pipeline.cli import build_parser, config_from_args
from rosebud.reskin.tile_pipeline.models import RunArtifacts, RunConfig, TileBatch
from rosebud.reskin.tile_pipeline import pipeline


def test_config_from_args_maps_cli_fields():
    parser = build_parser()
    args = parser.parse_args([
        '--atlas', 'Tiles0',
        '--theme', 'cozy',
        '--dry-run',
        '--type-only', 'water',
        '--workers', '3',
        '--stage', '2',
        '--anim-only', 'River',
        '--debug-atlas',
    ])

    config = config_from_args(args)

    assert config == RunConfig(
        atlas='Tiles0',
        theme_name='cozy',
        dry_run=True,
        type_only='water',
        fresh=False,
        workers=3,
        stage='2',
        anim_only='River',
        debug_atlas=True,
    )


def test_run_pipeline_debug_short_circuits(monkeypatch, tmp_path):
    calls = []
    config = RunConfig(atlas='Tiles0', theme_name='cozy', debug_atlas=True)
    artifacts = RunArtifacts(work_dir=tmp_path, atlas_path=tmp_path / 'Tiles0.png')

    monkeypatch.setattr(pipeline, 'load_env_and_theme', lambda cfg: calls.append('theme') or {'name': 'cozy'})
    monkeypatch.setattr(pipeline, 'prepare_run', lambda cfg: calls.append('prepare') or artifacts)
    monkeypatch.setattr(pipeline, 'extract_stage', lambda cfg, arts: calls.append('extract') or arts)
    monkeypatch.setattr(pipeline, 'debug_stage', lambda cfg, arts: calls.append('debug') or arts)

    result = pipeline.run_pipeline(config)

    assert result is artifacts
    assert calls == ['theme', 'prepare', 'extract', 'debug']


def test_run_pipeline_dry_run_batches_without_reskin(monkeypatch, tmp_path):
    calls = []
    config = RunConfig(atlas='Tiles0', theme_name='cozy', dry_run=True)
    artifacts = RunArtifacts(
        work_dir=tmp_path,
        atlas_path=tmp_path / 'Tiles0.png',
        cells=[],
        batches=[],
    )

    monkeypatch.setattr(pipeline, 'load_env_and_theme', lambda cfg: calls.append('theme') or {'name': 'cozy'})
    monkeypatch.setattr(pipeline, 'prepare_run', lambda cfg: calls.append('prepare') or artifacts)
    monkeypatch.setattr(pipeline, 'extract_stage', lambda cfg, arts: calls.append('extract') or arts)
    monkeypatch.setattr(pipeline, 'batch_stage', lambda cfg, arts: calls.append('batch') or arts)

    def fail(*args, **kwargs):
        raise AssertionError('unexpected stage call')

    monkeypatch.setattr(pipeline, 'anchor_stage', fail)
    monkeypatch.setattr(pipeline, 'reskin_stage', fail)
    monkeypatch.setattr(pipeline, 'assemble_stage', fail)

    result = pipeline.run_pipeline(config)

    assert result is artifacts
    assert calls == ['theme', 'prepare', 'extract', 'batch']


def test_tile_batch_round_trip_preserves_grid_positions():
    batch = TileBatch.from_legacy_dict({
        'batch_id': 'batch_000_plain',
        'tile_type': 'plain',
        'path': '/tmp/batch.png',
        'cells': [
            {
                'id': 'r000_c00',
                'row': 0,
                'col': 0,
                'x': 0,
                'y': 0,
                'type': 'plain',
                'path': '/tmp/cell.png',
                'grid_row': 2,
                'grid_col': 3,
            },
        ],
        'canvas_w': 100,
        'canvas_h': 100,
    })

    round_tripped = batch.to_legacy_dict()

    assert round_tripped['cells'][0]['grid_row'] == 2
    assert round_tripped['cells'][0]['grid_col'] == 3
