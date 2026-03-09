from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(slots=True)
class RunConfig:
    atlas: str
    theme_name: str
    dry_run: bool = False
    type_only: str | None = None
    fresh: bool = False
    workers: int = 16
    stage: str = "full"
    anim_only: str | None = None
    debug_atlas: bool = False


@dataclass(slots=True)
class AnimationMetadata:
    name: str | None = None
    frame_index: int | None = None
    cell_index: int | None = None


@dataclass(slots=True)
class TileCell:
    cell_id: str
    row: int
    col: int
    x: int
    y: int
    tile_type: str
    path: str
    grid_row: int | None = None
    grid_col: int | None = None
    is_animation_frame: bool = False
    animation: AnimationMetadata = field(default_factory=AnimationMetadata)

    @classmethod
    def from_legacy_dict(cls, data: dict[str, Any]) -> "TileCell":
        return cls(
            cell_id=data["id"],
            row=data["row"],
            col=data["col"],
            x=data["x"],
            y=data["y"],
            tile_type=data["type"],
            path=data["path"],
            grid_row=data.get("grid_row"),
            grid_col=data.get("grid_col"),
            is_animation_frame=data.get("is_anim_frame", False),
            animation=AnimationMetadata(
                name=data.get("anim_name"),
                frame_index=data.get("anim_frame_idx"),
                cell_index=data.get("anim_cell_idx"),
            ),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "id": self.cell_id,
            "row": self.row,
            "col": self.col,
            "x": self.x,
            "y": self.y,
            "type": self.tile_type,
            "path": self.path,
            "grid_row": self.grid_row,
            "grid_col": self.grid_col,
            "is_anim_frame": self.is_animation_frame,
            "anim_name": self.animation.name,
            "anim_frame_idx": self.animation.frame_index,
            "anim_cell_idx": self.animation.cell_index,
        }


@dataclass(slots=True)
class TileBatch:
    batch_id: str
    tile_type: str
    image_path: str
    cells: list[TileCell]
    is_animation_batch: bool = False
    animation_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy_dict(cls, data: dict[str, Any]) -> "TileBatch":
        return cls(
            batch_id=data["batch_id"],
            tile_type=data["tile_type"],
            image_path=data["path"],
            cells=[TileCell.from_legacy_dict(cell) for cell in data["cells"]],
            is_animation_batch=data.get("is_animation_batch", False),
            animation_name=data.get("anim_name"),
            metadata=dict(data),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        data = dict(self.metadata)
        data.update({
            "batch_id": self.batch_id,
            "tile_type": self.tile_type,
            "path": self.image_path,
            "cells": [cell.to_legacy_dict() for cell in self.cells],
            "is_animation_batch": self.is_animation_batch,
        })
        if self.animation_name is not None:
            data["anim_name"] = self.animation_name
        return data


@dataclass(slots=True)
class AnchorSet:
    paths: dict[str, str] = field(default_factory=dict)
    style_reference_sheet: str | None = None


@dataclass(slots=True)
class ReskinnedCell:
    cell: TileCell
    image: Image.Image


@dataclass(slots=True)
class RunArtifacts:
    work_dir: Path
    atlas_path: Path | None = None
    cells: list[TileCell] = field(default_factory=list)
    anchors: AnchorSet = field(default_factory=AnchorSet)
    batches: list[TileBatch] = field(default_factory=list)
    reskinned_cells: list[ReskinnedCell] = field(default_factory=list)
    final_output_path: Path | None = None
