from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image

from .anchors import generate_anchors, generate_style_reference_sheet
from .assemble import reassemble_atlas, update_reskin_manifest
from .batching import build_animation_batches, create_typed_batches
from .debug import generate_debug_atlas
from .extract import download_atlas, extract_cells
from .models import (
    AnchorSet,
    ReskinnedCell,
    RunArtifacts,
    RunConfig,
    TileBatch,
    TileCell,
)
from .postprocess import (
    extract_from_reskinned,
)
from .provider import reskin_batches


def load_env_and_theme(config: RunConfig) -> dict:
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

    theme_path = Path(__file__).parent.parent / 'themes' / f'{config.theme_name}.json'
    if not theme_path.exists():
        print(f'ERROR: Theme file not found: {theme_path}')
        sys.exit(1)
    theme = json.loads(theme_path.read_text())
    print(f"Theme: {theme['name']} — {theme['description']}")
    return theme


def prepare_run(config: RunConfig) -> RunArtifacts:
    work_dir = Path(__file__).parent.parent / 'output' / f'{config.atlas}_{config.theme_name}'
    work_dir.mkdir(parents=True, exist_ok=True)
    return RunArtifacts(work_dir=work_dir)


def extract_stage(config: RunConfig, artifacts: RunArtifacts) -> RunArtifacts:
    print('\n1. Downloading original atlas...')
    atlas_path = download_atlas(config.atlas, artifacts.work_dir)

    print('\n2. Extracting cells...')
    cells_manifest = artifacts.work_dir / 'cells_manifest.json'
    legacy_cells = None
    if cells_manifest.exists() and (artifacts.work_dir / 'cells').exists():
        cached = json.loads(cells_manifest.read_text())
        if cached and 'type' in cached[0]:
            print('  Using cached cells manifest')
            legacy_cells = cached
    if legacy_cells is None:
        legacy_cells = extract_cells(atlas_path, artifacts.work_dir)
        cells_manifest.write_text(json.dumps(legacy_cells, indent=2))

    artifacts.atlas_path = atlas_path
    artifacts.cells = [TileCell.from_legacy_dict(cell) for cell in legacy_cells]
    return artifacts


def anchor_stage(config: RunConfig, theme: dict, artifacts: RunArtifacts) -> RunArtifacts:
    if config.dry_run:
        return artifacts
    print('\n--- Stage 1: Generating anchor tiles ---')
    anchor_paths = generate_anchors([cell.to_legacy_dict() for cell in artifacts.cells], theme, artifacts.work_dir)

    print('\n--- Stage 1: Generating style reference sheet ---')
    style_sheet_path = str(generate_style_reference_sheet(anchor_paths, artifacts.work_dir))

    artifacts.anchors = AnchorSet(paths=anchor_paths, style_reference_sheet=style_sheet_path)
    return artifacts


def batch_stage(config: RunConfig, artifacts: RunArtifacts) -> RunArtifacts:
    print('\n3. Creating type-grouped batches...')
    type_batches = create_typed_batches([cell.to_legacy_dict() for cell in artifacts.cells], artifacts.work_dir)

    print('\n4. Creating animation batches...')
    anim_batches = build_animation_batches([cell.to_legacy_dict() for cell in artifacts.cells], artifacts.work_dir)

    batches = [TileBatch.from_legacy_dict(batch) for batch in (type_batches + anim_batches)]
    (artifacts.work_dir / 'batches_manifest.json').write_text(
        json.dumps([batch.to_legacy_dict() for batch in batches], indent=2)
    )
    artifacts.batches = batches
    return artifacts


def _load_cached_non_target_batches(target_batches: list[TileBatch], all_batches: list[TileBatch], reskinned_dir: Path) -> list[ReskinnedCell]:
    target_ids = {batch.batch_id for batch in target_batches}
    other_batches = [batch for batch in all_batches if batch.batch_id not in target_ids]
    results: list[ReskinnedCell] = []
    for batch in other_batches:
        rp = reskinned_dir / f'{batch.batch_id}_reskinned.png'
        if rp.exists():
            reskinned_img = Image.open(rp).convert('RGBA')
            extracted = extract_from_reskinned(reskinned_img, batch.to_legacy_dict())
            results.extend(ReskinnedCell(TileCell.from_legacy_dict(cell), image) for cell, image in extracted)
    return results


def reskin_stage(config: RunConfig, theme: dict, artifacts: RunArtifacts) -> RunArtifacts:
    if config.dry_run:
        return artifacts

    print('\n--- Stage 2: Full reskin + reassemble ---')
    reskinned_dir = artifacts.work_dir / 'reskinned'
    reskinned_dir.mkdir(exist_ok=True)

    if config.fresh:
        for file in reskinned_dir.iterdir():
            if config.type_only and config.type_only not in file.name:
                continue
            file.unlink()
        print('  Cleared cached reskinned batches')

    if config.stage == '2' and not artifacts.anchors.paths:
        anchor_paths = {}
        for tile_type in [
            'plain', 'street', 'rail', 'mountain', 'forest',
            'campsite', 'pier', 'water', 'river',
            'stormcloud', 'teleporter',
        ]:
            anchor_file = artifacts.work_dir / f'anchor_{tile_type}.png'
            if anchor_file.exists():
                anchor_paths[tile_type] = str(anchor_file)
        if not anchor_paths:
            print('ERROR: No anchor tiles found. Run --stage 1 first.')
            sys.exit(1)
        sheet_file = artifacts.work_dir / 'style_reference_sheet.png'
        style_sheet_path = str(sheet_file) if sheet_file.exists() else str(generate_style_reference_sheet(anchor_paths, artifacts.work_dir))
        artifacts.anchors = AnchorSet(paths=anchor_paths, style_reference_sheet=style_sheet_path)

    target_batches = artifacts.batches
    if config.anim_only:
        if config.anim_only == '*':
            target_batches = [b for b in artifacts.batches if b.is_animation_batch]
        else:
            target_batches = [
                b for b in artifacts.batches
                if b.is_animation_batch and b.animation_name == config.anim_only
            ]
        print(f'\n  Reskinning {len(target_batches)} animation batches...')
    elif config.type_only:
        target_batches = [b for b in artifacts.batches if b.tile_type == config.type_only]
        print(f'\n  Reskinning {len(target_batches)} {config.type_only} batches...')
    else:
        print(f'\n  Reskinning {len(target_batches)} batches with Gemini Flash...')

    extracted = reskin_batches(
        [batch.to_legacy_dict() for batch in target_batches],
        theme,
        reskinned_dir,
        config.workers,
        anchor_paths=artifacts.anchors.paths or None,
        style_sheet_path=artifacts.anchors.style_reference_sheet,
    )
    reskinned_cells = [ReskinnedCell(TileCell.from_legacy_dict(cell), image) for cell, image in extracted]

    if config.type_only or config.anim_only:
        reskinned_cells.extend(_load_cached_non_target_batches(target_batches, artifacts.batches, reskinned_dir))

    artifacts.reskinned_cells = reskinned_cells
    return artifacts


def assemble_stage(config: RunConfig, artifacts: RunArtifacts) -> RunArtifacts:
    if artifacts.atlas_path is None:
        return artifacts
    print(f'\n  Reassembling atlas ({len(artifacts.reskinned_cells)} cells)...')
    output_path = (
        Path(__file__).parent.parent
        / 'public' / 'reskin' / config.theme_name / f'{config.atlas}.png'
    )
    reassemble_atlas(
        artifacts.atlas_path,
        [(entry.cell.to_legacy_dict(), entry.image) for entry in artifacts.reskinned_cells],
        output_path,
    )
    update_reskin_manifest(config.atlas, config.theme_name, output_path)
    artifacts.final_output_path = output_path
    return artifacts


def debug_stage(config: RunConfig, artifacts: RunArtifacts) -> RunArtifacts:
    if artifacts.atlas_path is None:
        return artifacts
    print('\n--- Generating debug atlas overlays ---')
    original_out = artifacts.work_dir / 'debug_atlas.png'
    generate_debug_atlas(artifacts.atlas_path, [cell.to_legacy_dict() for cell in artifacts.cells], original_out)

    reskinned_path = (
        Path(__file__).parent.parent / 'public' / 'reskin' / config.theme_name / f'{config.atlas}.png'
    )
    if reskinned_path.exists():
        reskinned_out = artifacts.work_dir / 'debug_atlas_reskinned.png'
        generate_debug_atlas(reskinned_path, [cell.to_legacy_dict() for cell in artifacts.cells], reskinned_out)
    print('\nDebug atlas generation complete.')
    return artifacts


def run_pipeline(config: RunConfig) -> RunArtifacts:
    theme = load_env_and_theme(config)
    artifacts = prepare_run(config)
    artifacts = extract_stage(config, artifacts)

    if config.debug_atlas:
        return debug_stage(config, artifacts)

    if not config.dry_run and config.stage in ('1', 'full'):
        artifacts = anchor_stage(config, theme, artifacts)
        if config.stage == '1':
            print(f'\nStage 1 complete. Review anchor tiles at {artifacts.work_dir}/anchor_*.png')
            print('If anchors look good, run --stage 2.')
            return artifacts

    artifacts = batch_stage(config, artifacts)
    if config.dry_run:
        type_batches = len([b for b in artifacts.batches if not b.is_animation_batch])
        anim_batches = len([b for b in artifacts.batches if b.is_animation_batch])
        print(f'\nDry run complete. {len(artifacts.cells)} cells in {len(artifacts.batches)} batches ({type_batches} type + {anim_batches} animation).')
        print(f"Batch grids saved to {artifacts.work_dir / 'batches'}/")
        return artifacts

    if config.stage in ('2', 'full'):
        artifacts = reskin_stage(config, theme, artifacts)
        artifacts = assemble_stage(config, artifacts)
        if config.stage == '2' and artifacts.final_output_path is not None:
            print(f'\nStage 2 complete. Atlas reassembled at {artifacts.final_output_path}')
            print('Start dev server and playtest.')
            return artifacts

    if artifacts.final_output_path is not None:
        print(f'\nDone! Reskinned {config.atlas} with {config.theme_name} theme.')
        print(f'Output: {artifacts.final_output_path}')
    return artifacts
