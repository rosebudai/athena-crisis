from __future__ import annotations

import argparse

from .models import RunConfig
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Reskin tile atlases for Athena Crisis')
    parser.add_argument('--atlas', required=True, help='Atlas name (e.g. Tiles0)')
    parser.add_argument('--theme', required=True, help='Theme name (e.g. cozy)')
    parser.add_argument('--dry-run', action='store_true', help='Extract and batch only, no AI calls')
    parser.add_argument('--type-only', type=str, default=None, help='Process only this tile type (e.g. water, river, plain)')
    parser.add_argument('--fresh', action='store_true', help='Clear cached reskinned batches and regenerate')
    parser.add_argument('--workers', type=int, default=16, help='Number of parallel workers for API calls (default: 16)')
    parser.add_argument('--stage', type=str, default='full', choices=['1', '2', 'full'], help='Pipeline stage to run.')
    parser.add_argument('--skip-harmonize', action='store_true', help='Skip the transition-tile color harmonization step')
    parser.add_argument('--skip-composite', action='store_true', help='Skip the background compositing step (grass pixel replacement)')
    parser.add_argument('--anim-only', type=str, nargs='?', const='*', default=None, help='Process only animation batches. Optionally specify a name (e.g. Sea, River). Use without a value to run all animations.')
    parser.add_argument('--debug-atlas', action='store_true', help='Generate labeled overlay PNGs of the atlas and exit (no pipeline run)')
    return parser


def config_from_args(args: argparse.Namespace) -> RunConfig:
    return RunConfig(
        atlas=args.atlas,
        theme_name=args.theme,
        dry_run=args.dry_run,
        type_only=args.type_only,
        fresh=args.fresh,
        workers=args.workers,
        stage=args.stage,
        skip_harmonize=args.skip_harmonize,
        skip_composite=args.skip_composite,
        anim_only=args.anim_only,
        debug_atlas=args.debug_atlas,
    )


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_pipeline(config_from_args(args))
