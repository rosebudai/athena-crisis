from __future__ import annotations

import numpy as np
from PIL import Image

# Atlas constants
TILE_SIZE = 24
ATLAS_COLS = 12
CDN_BASE = "https://art.athenacrisis.com/v19/assets/render"

# Batch grid constants
GRID_COLS = 6
CELLS_PER_BATCH = 36  # 6x6
CELL_PADDING = 4
GRID_LINE_WIDTH = 2
BG_COLOR = (200, 200, 200, 255)
LINE_COLOR = (0, 0, 0, 255)

# Animation definitions from athena/info/Tile.tsx.
# For each animated tile: (base_col, base_row, frames, offset, horizontal, block_start_delta).
# block_start_delta: the frame block starts at base_row + block_start_delta.
#   -1 for tiles using AreaModifiers (modifier y range [-1, 1])
#    0 for tiles whose modifiers start at y=0
# After reskinning, base-frame pixels are copied to all other frames so that
# independently-reskinned frames don't flicker with different art styles.
ANIMATED_TILES = [
    # name              base_col  base_row  frames  offset  horizontal  block_start_delta
    ("Sea",                  8,       35,      4,      3,    False,      -1),
    ("DeepSea",              8,       47,      4,      3,    False,      -1),
    ("Beach",                3,       50,      4,      6,    False,      -1),
    ("River",                1,       73,     24,      3,    False,       0),
    ("Pier",                 0,       29,      4,      5,    False,       0),
    ("Campsite",             0,       28,      4,      1,    True,        0),
    ("StormCloud",           6,        7,      4,      3,    False,      -1),
    ("Reef",                 5,       18,      4,      1,    True,        0),
    ("Lightning",           10,        0,      4,      1,    False,       0),
    ("LightningV",          10,        6,      4,      1,    False,       0),
    ("RailBridge",           5,        0,      4,      1,    False,       0),
    ("GasBubbles",           5,       26,      4,      1,    True,        0),
    ("Teleporter",           0,       25,      2,      1,    False,       0),
    ("Computer",             0,       31,      4,      1,    False,       0),
    ("FloatingWaterEdge",    7,       58,      4,      2,    False,       0),
    ("Island",               5,       23,      4,      1,    True,        0),
    ("Iceberg/Weeds",        5,       22,      4,      1,    True,        0),
    # FloatingEdge border animations (getFloatingEdgeAnimation in Tile.tsx)
    # Waterfall modifiers on FloatingEdge (base sprite(8,32) + modifier offsets)
    # Absolute positions: cols 8-10, rows 73-75.  WaterfallAnimation = River anim.
    ("FE_Waterfall",         9,       73,     24,      3,    False,       0),
    # Sea wall decorators on FloatingEdge — offset=1, frames=4
    # Absolute: (9,12),(10,12) and (9,16),(10,16) — two separate row groups
    ("FE_WallDecorA",        9,       12,      4,      1,    False,       0),
    ("FE_WallDecorB",        9,       16,      4,      1,    False,       0),
    # Sea area decorators on FloatingEdge — offset=2, frames=4
    # Absolute: (9,20),(10,20),(9,21),(10,21) — 2-row base block
    ("FE_AreaDecor",         9,       20,      4,      2,    False,       0),
]

# Per-cell type mapping — derived from sprite positions in athena/info/Tile.tsx.
# Every occupied (col, row) in the Tiles0 atlas is mapped to a semantic type.
# Types: plain, street, mountain, forest, campsite, pier, water, river,
#        stormcloud, reef, sea_object, trench, bridge, rail, teleporter,
#        computer, floatingedge, lightning, pipe.
TILE_CELL_MAP: dict[tuple[int, int], str] = {
    # --- Rows 0-2: Plain, Rail, Bridge, Lightning ---
    (0, 0): "plain", (1, 0): "plain", (2, 0): "plain", (5, 0): "rail", (6, 0): "rail", (7, 0): "rail", (8, 0): "plain", (9, 0): "floatingedge", (10, 0): "lightning", (11, 0): "rail",
    (0, 1): "plain", (1, 1): "plain", (2, 1): "plain", (3, 1): "plain", (4, 1): "plain", (5, 1): "rail", (6, 1): "rail", (7, 1): "rail", (8, 1): "bridge", (9, 1): "floatingedge", (10, 1): "lightning", (11, 1): "rail",
    (0, 2): "plain", (1, 2): "plain", (2, 2): "plain", (5, 2): "rail", (6, 2): "rail", (7, 2): "rail", (8, 2): "bridge", (9, 2): "floatingedge", (10, 2): "lightning", (11, 2): "rail",
    # --- Rows 3-5: Street, Rail, Bridge ---
    (0, 3): "street", (1, 3): "street", (2, 3): "street", (3, 3): "street", (4, 3): "street", (5, 3): "rail", (6, 3): "rail", (7, 3): "rail", (8, 3): "bridge", (9, 3): "floatingedge", (10, 3): "lightning", (11, 3): "rail",
    (0, 4): "street", (1, 4): "street", (2, 4): "street", (3, 4): "street", (4, 4): "street", (5, 4): "rail", (6, 4): "rail", (7, 4): "rail", (8, 4): "bridge",
    (0, 5): "street", (1, 5): "street", (2, 5): "street", (3, 5): "street", (4, 5): "street", (5, 5): "bridge", (6, 5): "bridge", (7, 5): "bridge", (8, 5): "bridge",
    # --- Row 6: Mountain/StormCloud boundary ---
    (0, 6): "mountain", (3, 6): "mountain", (4, 6): "mountain", (5, 6): "stormcloud", (6, 6): "stormcloud", (7, 6): "stormcloud", (10, 6): "lightning",
    # --- Rows 7-13: Mountain + StormCloud ---
    (0, 7): "mountain", (1, 7): "mountain", (2, 7): "mountain", (3, 7): "mountain", (4, 7): "mountain", (5, 7): "stormcloud", (6, 7): "stormcloud", (7, 7): "stormcloud", (8, 7): "stormcloud", (10, 7): "lightning",
    (0, 8): "mountain", (1, 8): "mountain", (2, 8): "mountain", (3, 8): "mountain", (4, 8): "mountain", (5, 8): "stormcloud", (6, 8): "stormcloud", (7, 8): "stormcloud", (8, 8): "stormcloud", (9, 8): "floatingedge", (10, 8): "lightning", (11, 8): "lightning",
    (0, 9): "mountain", (1, 9): "mountain", (2, 9): "mountain", (3, 9): "mountain", (4, 9): "mountain", (5, 9): "stormcloud", (6, 9): "stormcloud", (7, 9): "stormcloud", (9, 9): "floatingedge", (10, 9): "lightning", (11, 9): "lightning",
    (0, 10): "mountain", (3, 10): "mountain", (4, 10): "mountain", (5, 10): "stormcloud", (6, 10): "stormcloud", (7, 10): "stormcloud", (8, 10): "stormcloud", (9, 10): "floatingedge", (11, 10): "stormcloud",
    (0, 11): "mountain", (1, 11): "mountain", (2, 11): "mountain", (3, 11): "mountain", (4, 11): "mountain", (5, 11): "stormcloud", (6, 11): "stormcloud", (7, 11): "stormcloud", (8, 11): "stormcloud", (9, 11): "floatingedge", (11, 11): "stormcloud",
    (0, 12): "mountain", (1, 12): "mountain", (2, 12): "mountain", (3, 12): "mountain", (4, 12): "mountain", (5, 12): "stormcloud", (6, 12): "stormcloud", (7, 12): "stormcloud", (9, 12): "floatingedge", (10, 12): "floatingedge",
    (0, 13): "mountain", (1, 13): "mountain", (2, 13): "mountain", (3, 13): "mountain", (4, 13): "mountain", (5, 13): "stormcloud", (6, 13): "stormcloud", (7, 13): "stormcloud", (8, 13): "stormcloud", (9, 13): "floatingedge", (10, 13): "floatingedge",
    # --- Rows 14-17: Trench + StormCloud ---
    (0, 14): "trench", (5, 14): "stormcloud", (6, 14): "stormcloud", (7, 14): "stormcloud", (8, 14): "stormcloud", (9, 14): "floatingedge", (10, 14): "floatingedge",
    (0, 15): "trench", (1, 15): "trench", (2, 15): "trench", (3, 15): "trench", (4, 15): "trench", (5, 15): "stormcloud", (6, 15): "stormcloud", (7, 15): "stormcloud", (9, 15): "floatingedge", (10, 15): "floatingedge",
    (0, 16): "trench", (1, 16): "trench", (2, 16): "trench", (3, 16): "trench", (4, 16): "trench", (5, 16): "stormcloud", (6, 16): "stormcloud", (7, 16): "stormcloud", (8, 16): "stormcloud", (9, 16): "floatingedge", (10, 16): "floatingedge",
    (0, 17): "trench", (1, 17): "trench", (2, 17): "trench", (5, 17): "stormcloud", (6, 17): "stormcloud", (7, 17): "stormcloud", (8, 17): "stormcloud", (9, 17): "floatingedge", (10, 17): "floatingedge",
    # --- Rows 18-21: Forest + Reef ---
    (0, 18): "forest", (5, 18): "reef", (6, 18): "reef", (7, 18): "reef", (8, 18): "reef", (9, 18): "floatingedge", (10, 18): "floatingedge",
    (0, 19): "forest", (1, 19): "forest", (2, 19): "forest", (3, 19): "forest", (4, 19): "forest", (5, 19): "reef", (6, 19): "reef", (7, 19): "reef", (8, 19): "reef", (9, 19): "floatingedge", (10, 19): "floatingedge",
    (0, 20): "forest", (1, 20): "forest", (2, 20): "forest", (3, 20): "forest", (4, 20): "forest", (5, 20): "reef", (6, 20): "reef", (7, 20): "reef", (8, 20): "reef", (9, 20): "floatingedge", (10, 20): "floatingedge",
    (0, 21): "forest", (1, 21): "forest", (2, 21): "forest", (3, 21): "forest", (4, 21): "forest", (5, 21): "reef", (6, 21): "reef", (7, 21): "reef", (8, 21): "reef", (9, 21): "floatingedge", (10, 21): "floatingedge",
    # --- Rows 22-25: Forest + Sea Object ---
    (0, 22): "forest", (5, 22): "sea_object", (6, 22): "sea_object", (7, 22): "sea_object", (8, 22): "sea_object", (9, 22): "floatingedge", (10, 22): "floatingedge",
    (0, 23): "forest", (1, 23): "forest", (2, 23): "forest", (3, 23): "forest", (4, 23): "forest", (5, 23): "sea_object", (6, 23): "sea_object", (7, 23): "sea_object", (8, 23): "sea_object", (9, 23): "floatingedge", (10, 23): "floatingedge",
    (0, 24): "forest", (1, 24): "forest", (2, 24): "forest", (3, 24): "forest", (4, 24): "forest", (5, 24): "sea_object", (6, 24): "sea_object", (7, 24): "sea_object", (8, 24): "sea_object", (9, 24): "floatingedge", (10, 24): "floatingedge",
    (0, 25): "forest", (1, 25): "forest", (2, 25): "forest", (3, 25): "forest", (4, 25): "forest", (5, 25): "sea_object", (6, 25): "sea_object", (7, 25): "sea_object", (8, 25): "sea_object", (9, 25): "floatingedge", (10, 25): "floatingedge",
    # --- Row 26: Teleporter + Sea Object ---
    (0, 26): "teleporter", (1, 26): "teleporter", (2, 26): "teleporter", (3, 26): "teleporter", (5, 26): "sea_object", (6, 26): "sea_object", (7, 26): "sea_object", (8, 26): "sea_object", (9, 26): "floatingedge", (10, 26): "floatingedge",
    # --- Rows 27-28: Pipe, Campsite, Sea Object, Rail ---
    (0, 27): "pipe", (1, 27): "pipe", (2, 27): "pipe", (3, 27): "pipe", (5, 27): "sea_object", (6, 27): "sea_object", (7, 27): "sea_object", (8, 27): "sea_object", (9, 27): "floatingedge", (10, 27): "floatingedge", (11, 27): "rail",
    (0, 28): "campsite", (1, 28): "campsite", (2, 28): "campsite", (3, 28): "pipe", (5, 28): "rail", (6, 28): "rail", (7, 28): "rail", (8, 28): "rail", (9, 28): "rail", (10, 28): "rail", (11, 28): "rail",
    # --- Rows 29-34: Pier, Rail, Computer, FloatingEdge, Water ---
    (0, 29): "pier", (2, 29): "pier", (3, 29): "pier", (4, 29): "pier", (5, 29): "pier", (6, 29): "pier", (7, 29): "rail", (8, 29): "rail", (9, 29): "rail", (10, 29): "rail", (11, 29): "rail",
    (1, 30): "pier", (2, 30): "pier", (3, 30): "pier", (4, 30): "pier", (5, 30): "pier", (6, 30): "pier", (7, 30): "pier", (8, 30): "pier", (9, 30): "pier", (10, 30): "rail", (11, 30): "rail",
    (0, 31): "computer", (1, 31): "computer", (2, 31): "pier", (3, 31): "pier", (4, 31): "pier", (7, 31): "floatingedge", (8, 31): "floatingedge", (9, 31): "floatingedge", (10, 31): "floatingedge", (11, 31): "floatingedge",
    (0, 32): "pier", (1, 32): "pier", (2, 32): "pier", (3, 32): "pier", (5, 32): "pier", (6, 32): "pier", (7, 32): "floatingedge", (9, 32): "floatingedge", (10, 32): "floatingedge", (11, 32): "floatingedge",
    (0, 33): "pier", (5, 33): "pier", (6, 33): "pier", (7, 33): "floatingedge", (8, 33): "floatingedge", (9, 33): "floatingedge",
    (0, 34): "pier", (2, 34): "pier", (3, 34): "pier", (4, 34): "pier", (5, 34): "pier", (6, 34): "pier", (7, 34): "water", (8, 34): "water", (9, 34): "water", (10, 34): "water", (11, 34): "water",
    # --- Rows 35-48: Pier animation + Water (Sea/DeepSea) ---
    (1, 35): "pier", (2, 35): "pier", (3, 35): "pier", (4, 35): "pier", (5, 35): "pier", (6, 35): "pier", (7, 35): "water", (8, 35): "water", (9, 35): "water", (10, 35): "water", (11, 35): "water",
    (0, 36): "pier", (1, 36): "pier", (2, 36): "pier", (3, 36): "pier", (4, 36): "pier", (7, 36): "water", (8, 36): "water", (9, 36): "water",
    (0, 37): "pier", (1, 37): "pier", (2, 37): "pier", (3, 37): "pier", (5, 37): "pier", (6, 37): "pier", (7, 37): "water", (8, 37): "water", (9, 37): "water", (10, 37): "water", (11, 37): "water",
    (0, 38): "pier", (5, 38): "pier", (6, 38): "pier", (7, 38): "water", (8, 38): "water", (9, 38): "water", (10, 38): "water", (11, 38): "water",
    (0, 39): "pier", (2, 39): "pier", (3, 39): "pier", (4, 39): "pier", (5, 39): "pier", (6, 39): "pier", (7, 39): "water", (8, 39): "water", (9, 39): "water",
    (1, 40): "pier", (2, 40): "pier", (3, 40): "pier", (4, 40): "pier", (5, 40): "pier", (6, 40): "pier", (7, 40): "water", (8, 40): "water", (9, 40): "water", (10, 40): "water", (11, 40): "water",
    (0, 41): "pier", (1, 41): "pier", (2, 41): "pier", (3, 41): "pier", (4, 41): "pier", (7, 41): "water", (8, 41): "water", (9, 41): "water", (10, 41): "water", (11, 41): "water",
    (0, 42): "pier", (1, 42): "pier", (2, 42): "pier", (3, 42): "pier", (5, 42): "pier", (6, 42): "pier", (7, 42): "water", (8, 42): "water", (9, 42): "water",
    (0, 43): "pier", (5, 43): "pier", (6, 43): "pier", (7, 43): "water", (8, 43): "water", (9, 43): "water", (10, 43): "water", (11, 43): "water",
    (0, 44): "pier", (2, 44): "pier", (3, 44): "pier", (4, 44): "pier", (5, 44): "pier", (6, 44): "pier", (7, 44): "water", (8, 44): "water", (9, 44): "water", (10, 44): "water", (11, 44): "water",
    (1, 45): "pier", (2, 45): "pier", (3, 45): "pier", (4, 45): "pier", (5, 45): "pier", (6, 45): "pier", (7, 45): "water", (8, 45): "water", (9, 45): "water",
    (0, 46): "pier", (1, 46): "pier", (2, 46): "pier", (3, 46): "pier", (4, 46): "pier", (7, 46): "water", (8, 46): "water", (9, 46): "water", (10, 46): "water", (11, 46): "water",
    (0, 47): "pier", (1, 47): "pier", (2, 47): "pier", (3, 47): "pier", (5, 47): "pier", (6, 47): "pier", (7, 47): "water", (8, 47): "water", (9, 47): "water", (10, 47): "water", (11, 47): "water",
    (0, 48): "pier", (5, 48): "pier", (6, 48): "pier", (7, 48): "water", (8, 48): "water", (9, 48): "water",
    # --- Rows 49-72: Water (Beach + Deep Sea) ---
    # FloatingWaterEdge at r58-65 c7-10
    (0, 49): "water", (1, 49): "water", (2, 49): "water", (3, 49): "water", (4, 49): "water", (5, 49): "water", (6, 49): "water", (7, 49): "water", (8, 49): "water", (9, 49): "water", (10, 49): "water", (11, 49): "water",
    (0, 50): "water", (1, 50): "water", (2, 50): "water", (3, 50): "water", (4, 50): "water", (5, 50): "water", (6, 50): "water", (7, 50): "water", (8, 50): "water", (9, 50): "water", (10, 50): "water", (11, 50): "water",
    (0, 51): "water", (1, 51): "water", (2, 51): "water", (3, 51): "water", (4, 51): "water", (5, 51): "water", (6, 51): "water", (7, 51): "water", (8, 51): "water", (9, 51): "water",
    (0, 52): "water", (1, 52): "water", (2, 52): "water", (3, 52): "water", (4, 52): "water", (5, 52): "water", (6, 52): "water", (7, 52): "water", (8, 52): "water", (9, 52): "water", (10, 52): "water", (11, 52): "water",
    (0, 53): "water", (1, 53): "water", (2, 53): "water", (3, 53): "water", (4, 53): "water", (5, 53): "water", (6, 53): "water", (7, 53): "water", (8, 53): "water", (9, 53): "water", (10, 53): "water", (11, 53): "water",
    (0, 54): "water", (1, 54): "water", (2, 54): "water", (3, 54): "water", (4, 54): "water", (5, 54): "water", (6, 54): "water", (7, 54): "water", (8, 54): "water", (9, 54): "water",
    (0, 55): "water", (1, 55): "water", (2, 55): "water", (3, 55): "water", (4, 55): "water", (5, 55): "water", (6, 55): "water", (7, 55): "water", (8, 55): "water", (9, 55): "water", (10, 55): "water", (11, 55): "water",
    (0, 56): "water", (1, 56): "water", (2, 56): "water", (3, 56): "water", (4, 56): "water", (5, 56): "water", (6, 56): "water", (7, 56): "water", (8, 56): "water", (9, 56): "water", (10, 56): "water", (11, 56): "water",
    (0, 57): "water", (1, 57): "water", (2, 57): "water", (3, 57): "water", (4, 57): "water", (5, 57): "water", (6, 57): "water", (7, 57): "water", (8, 57): "water", (9, 57): "water",
    (0, 58): "water", (1, 58): "water", (2, 58): "water", (3, 58): "water", (4, 58): "water", (5, 58): "water", (6, 58): "water", (7, 58): "floatingedge", (8, 58): "floatingedge", (9, 58): "floatingedge", (10, 58): "floatingedge",
    (0, 59): "water", (1, 59): "water", (2, 59): "water", (3, 59): "water", (4, 59): "water", (5, 59): "water", (6, 59): "water", (7, 59): "floatingedge", (8, 59): "floatingedge", (9, 59): "floatingedge", (10, 59): "floatingedge",
    (0, 60): "water", (1, 60): "water", (2, 60): "water", (3, 60): "water", (4, 60): "water", (5, 60): "water", (6, 60): "water", (7, 60): "floatingedge", (8, 60): "floatingedge", (9, 60): "floatingedge", (10, 60): "floatingedge",
    (0, 61): "water", (1, 61): "water", (2, 61): "water", (3, 61): "water", (4, 61): "water", (5, 61): "water", (6, 61): "water", (7, 61): "floatingedge", (8, 61): "floatingedge", (9, 61): "floatingedge", (10, 61): "floatingedge",
    (0, 62): "water", (1, 62): "water", (2, 62): "water", (3, 62): "water", (4, 62): "water", (5, 62): "water", (6, 62): "water", (7, 62): "floatingedge", (8, 62): "floatingedge", (9, 62): "floatingedge", (10, 62): "floatingedge",
    (0, 63): "water", (1, 63): "water", (2, 63): "water", (3, 63): "water", (4, 63): "water", (5, 63): "water", (6, 63): "water", (7, 63): "floatingedge", (8, 63): "floatingedge", (9, 63): "floatingedge", (10, 63): "floatingedge",
    (0, 64): "water", (1, 64): "water", (2, 64): "water", (3, 64): "water", (4, 64): "water", (5, 64): "water", (6, 64): "water", (7, 64): "floatingedge", (8, 64): "floatingedge", (9, 64): "floatingedge", (10, 64): "floatingedge",
    (0, 65): "water", (1, 65): "water", (2, 65): "water", (3, 65): "water", (4, 65): "water", (5, 65): "water", (6, 65): "water", (7, 65): "floatingedge", (8, 65): "floatingedge", (9, 65): "floatingedge", (10, 65): "floatingedge",
    (0, 66): "water", (1, 66): "water", (2, 66): "water", (3, 66): "water", (4, 66): "water", (5, 66): "water", (6, 66): "water",
    (0, 67): "water", (1, 67): "water", (2, 67): "water", (3, 67): "water", (4, 67): "water", (5, 67): "water", (6, 67): "water",
    (0, 68): "water", (1, 68): "water", (2, 68): "water", (3, 68): "water", (4, 68): "water", (5, 68): "water", (6, 68): "water",
    (0, 69): "water", (1, 69): "water", (2, 69): "water", (3, 69): "water", (4, 69): "water", (5, 69): "water", (6, 69): "water",
    (0, 70): "water", (1, 70): "water", (2, 70): "water", (3, 70): "water", (4, 70): "water", (5, 70): "water", (6, 70): "water",
    (0, 71): "water", (1, 71): "water", (2, 71): "water", (3, 71): "water", (4, 71): "water", (5, 71): "water", (6, 71): "water",
    (0, 72): "water", (1, 72): "water", (2, 72): "water", (3, 72): "water", (4, 72): "water", (5, 72): "water", (6, 72): "water",
    # --- Rows 73-144: River (repeating 3-row pattern) ---
    # Pattern per 3-row group (base, base+1, base+2):
    #   base+0: c0-4=river, c6=water(sea anim), c9=floatingedge
    #   base+1: c0,c2-4=river, c5=water, c7=water, c8=floatingedge, c10=floatingedge
    #   base+2: c0-3=river, c6=water, c9=floatingedge
    **{
        (col, row): typ
        for base in range(73, 145, 3)
        for row, col_types in [
            (base, [(c, "river") for c in range(0, 5)]
                 + [(6, "water"), (9, "floatingedge")]),
            (base + 1, [(0, "river")] + [(c, "river") for c in range(2, 5)]
                     + [(5, "water"), (7, "water"), (8, "floatingedge"), (10, "floatingedge")]),
            (base + 2, [(c, "river") for c in range(0, 4)]
                     + [(6, "water"), (9, "floatingedge")]),
        ]
        if row <= 144
        for col, typ in col_types
    },
}

# Sub-types that inherit their anchor from a parent type.
# Types not listed here generate their own anchor.
ANCHOR_INHERITANCE: dict[str, str] = {
    "trench": "plain",
    "bridge": "street",
    "pipe": "street",
    "computer": "street",
    "lightning": "plain",
    "floatingedge": "water",
    "sea_object": "water",
    "reef": "water",
}

# Per-cell descriptions for tiles in "street sub-type" groups (street, rail,
# trench, bridge, pipe, computer).  Used to build a per-cell legend that is
# injected into the Gemini prompt so the model knows what each tile depicts.
# Keys are (col, row) atlas positions; values are short human-readable labels.
TILE_DESCRIPTIONS: dict[tuple[int, int], str] = {
    # --- Street (rows 3-6, cols 0-4) ---
    # Street uses JoinableModifiers with base position sprite(3, 3).
    (0, 3): "road top-left corner, turns from south to east",
    (1, 3): "road T-junction, connects east/west/south (open bottom)",
    (2, 3): "road top-right corner, turns from south to west",
    (3, 3): "road straight horizontal, connects east-west",
    (4, 3): "road straight vertical, connects north-south",
    (0, 4): "road T-junction, connects north/south/east (open right)",
    (1, 4): "road 4-way crossroads intersection",
    (2, 4): "road T-junction, connects north/south/west (open left)",
    (3, 4): "road end-cap or tail facing east",
    (4, 4): "road end-cap or tail facing south",
    (0, 5): "road bottom-left corner, turns from north to east",
    (1, 5): "road T-junction, connects east/west/north (open top)",
    (2, 5): "road bottom-right corner, turns from north to west",
    (3, 5): "road end-cap or tail facing west",
    (4, 5): "road end-cap or tail facing north",

    # --- Rail / RailTrack (base sprite(10, 28), JoinableModifiers) ---
    # RailBridge base sprite(5, 0) occupies rows 0-4 cols 5-7.
    (5, 0): "rail bridge single span, isolated rail bridge segment",
    (6, 0): "rail bridge vertical single, short vertical rail bridge",
    (7, 0): "rail bridge vertical, full vertical rail bridge span",
    (11, 0): "rail track variant, isolated rail segment",
    (5, 1): "rail bridge tail facing left, left end of rail bridge",
    (6, 1): "rail bridge horizontal, full horizontal rail bridge span",
    (7, 1): "rail bridge tail facing right, right end of rail bridge",
    (11, 1): "rail track variant, rail segment",
    (5, 2): "rail bridge connecting tail up, vertical bridge end top",
    (6, 2): "rail bridge crossing vertical, rail bridge over crossing",
    (7, 2): "rail bridge connecting tail right, bridge end right",
    (11, 2): "rail track variant, rail segment",
    (5, 3): "rail bridge connecting tail down, vertical bridge end bottom",
    (6, 3): "rail bridge horizontal crossing, bridge over crossing",
    (7, 3): "rail bridge connecting tail left, bridge end left",
    (11, 3): "rail track variant, rail segment",
    (5, 4): "rail bridge variant, rail bridge segment over water",
    (6, 4): "rail bridge variant, rail bridge segment",
    (7, 4): "rail bridge variant, rail bridge end piece",
    (11, 27): "rail track single, isolated rail track segment",
    (5, 28): "rail track crossing horizontal, rail crosses road horizontally",
    (6, 28): "rail track crossing vertical, rail crosses road vertically",
    (7, 28): "rail track top-left corner, turns from south to east",
    (8, 28): "rail track T-junction bottom, connects east/west/south",
    (9, 28): "rail track top-right corner, turns from south to west",
    (10, 28): "rail track straight horizontal, connects east-west",
    (11, 28): "rail track straight vertical, connects north-south",
    (7, 29): "rail track T-junction right, connects north/south/east",
    (8, 29): "rail track 4-way crossroads intersection",
    (9, 29): "rail track T-junction left, connects north/south/west",
    (10, 29): "rail track end-cap or tail facing east",
    (11, 29): "rail track end-cap or tail facing south",
    (10, 30): "rail track end-cap or tail facing west",
    (11, 30): "rail track end-cap or tail facing north",

    # --- Trench (base sprite(1, 16), AreaModifiers) ---
    # Trench Single modifier at sprite(-1, -2) -> (0, 14).
    (0, 14): "trench isolated single, standalone dug fortification",
    (0, 15): "trench top-left area corner, fortification corner NW",
    (1, 15): "trench top wall, fortification edge facing north",
    (2, 15): "trench top-right area corner, fortification corner NE",
    (3, 15): "trench bottom-right edge transition, inner corner SE",
    (4, 15): "trench bottom-left edge transition, inner corner SW",
    (0, 16): "trench left wall, fortification edge facing west",
    (1, 16): "trench center, open fortification interior",
    (2, 16): "trench right wall, fortification edge facing east",
    (3, 16): "trench top-right edge transition, inner corner NE",
    (4, 16): "trench top-left edge transition, inner corner NW",
    (0, 17): "trench bottom-left area corner, fortification corner SW",
    (1, 17): "trench bottom wall, fortification edge facing south",
    (2, 17): "trench bottom-right area corner, fortification corner SE",

    # --- Bridge (base sprite(5, 5), various modifiers) ---
    (8, 1): "bridge vertical single, short vertical bridge over gap",
    (8, 2): "bridge connecting tail up, vertical bridge top end",
    (8, 3): "bridge vertical, full vertical bridge span",
    (8, 4): "bridge connecting tail down, vertical bridge bottom end",
    (5, 5): "bridge single, isolated bridge segment",
    (6, 5): "bridge tail facing left, left end of bridge deck",
    (7, 5): "bridge horizontal, full horizontal bridge span",
    (8, 5): "bridge tail facing right, right end of bridge deck",

    # --- Pipe (base sprite(5, 29), offsets into rows 27-28) ---
    (0, 27): "pipe top-left corner, turns from south to east",
    (1, 27): "pipe straight vertical, connects north-south",
    (2, 27): "pipe top-right corner, turns from south to west",
    (3, 27): "pipe straight horizontal, connects east-west",
    (3, 28): "pipe end-cap or tail facing right",

    # --- Computer (base sprite(0, 31), with Variant2 modifier) ---
    (0, 31): "computer terminal base, primary display unit",
    (1, 31): "computer terminal variant, secondary display unit",
}



# Short abbreviations for tile types, used in debug atlas overlays.
TYPE_ABBREV: dict[str, str] = {
    "plain": "pln", "street": "str", "mountain": "mtn", "forest": "for",
    "campsite": "cmp", "pier": "pir", "water": "wat", "river": "riv",
    "stormcloud": "cld", "reef": "ref", "sea_object": "sea", "trench": "trn",
    "bridge": "brg", "rail": "ral", "teleporter": "tel", "computer": "cpu",
    "pipe": "pip", "floatingedge": "fe", "lightning": "lit",
}

def classify_cell(col: int, row: int) -> str | None:
    """Classify a cell by its (col, row) position into a tile type group.

    Returns None if the cell is not in TILE_CELL_MAP.
    """
    return TILE_CELL_MAP.get((col, row))


# Pre-compute non-base animation frame positions for fast lookup.
# Animation frame (col, row) pairs are computed from the actual atlas in
# compute_anim_frame_set() — this avoids the row-overlap issue where
# different tile types share atlas rows but use different columns.
_anim_frame_set: set[tuple[int, int]] | None = None


def compute_anim_frame_set(atlas_img: Image.Image) -> set[tuple[int, int]]:
    """Scan the atlas to determine which (col, row) cells are animation frames.

    For each animation, the base frame block occupies `offset` contiguous rows
    starting at `base_row + block_start_delta`. Every non-empty cell in the
    base block (within the animation's column range) has corresponding animation
    frame cells at row + i*offset for i = 1..frames-1. We mark those as
    animation frames to exclude from AI batching.

    Column ranges from _ANIM_COL_OFFSETS prevent false positives where different
    tile types share the same atlas rows but use different column ranges.
    """
    anim_frames: set[tuple[int, int]] = set()
    atlas_arr = np.array(atlas_img)

    for entry in ANIMATED_TILES:
        name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
        if horizontal:
            for i in range(1, frames):
                anim_frames.add((base_col + i * offset, base_row))
        else:
            min_x, max_x = _ANIM_COL_OFFSETS.get(name, (-3, 6))
            block_start = base_row + block_start_delta
            for row_delta in range(offset):
                src_row = block_start + row_delta
                if src_row < 0 or src_row * TILE_SIZE >= atlas_arr.shape[0]:
                    continue
                for col_offset in range(min_x, max_x + 1):
                    col = base_col + col_offset
                    if not (0 <= col < ATLAS_COLS):
                        continue
                    # Check if cell is non-empty in original atlas
                    y0 = src_row * TILE_SIZE
                    x0 = col * TILE_SIZE
                    cell_alpha = atlas_arr[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE, 3]
                    if cell_alpha.max() == 0:
                        continue
                    # Mark corresponding cells in non-base frames
                    for i in range(1, frames):
                        anim_frames.add((col, src_row + i * offset))

    return anim_frames


# ---------------------------------------------------------------------------
# Color-space conversion helpers (sRGB <-> CIELAB via D65 XYZ)
# ---------------------------------------------------------------------------

def _rgb_to_lab(rgb_array: np.ndarray) -> np.ndarray:
    """Convert RGB (0-255) array to CIELAB. Shape: (N, 3) -> (N, 3).

    Pipeline: sRGB uint8 -> linear RGB -> XYZ (D65) -> CIELAB.
    """
    # Normalize to 0-1 and apply sRGB companding (inverse gamma)
    rgb = rgb_array.astype(np.float64) / 255.0
    mask = rgb > 0.04045
    rgb = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)

    # Linear RGB -> XYZ (sRGB D65 matrix)
    #   http://www.brucelindbloom.com/index.html?Eqn_RGB_XYZ_Matrix.html
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = rgb @ m.T  # (N, 3)

    # Normalize by D65 white point
    d65 = np.array([0.95047, 1.00000, 1.08883])
    xyz = xyz / d65

    # XYZ -> LAB
    epsilon = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    f = np.where(xyz > epsilon, np.cbrt(xyz), (kappa * xyz + 16.0) / 116.0)

    L = 116.0 * f[:, 1] - 16.0
    a = 500.0 * (f[:, 0] - f[:, 1])
    b = 200.0 * (f[:, 1] - f[:, 2])

    return np.stack([L, a, b], axis=1)


def _lab_to_rgb(lab_array: np.ndarray) -> np.ndarray:
    """Convert CIELAB array to RGB (0-255). Shape: (N, 3) -> (N, 3) uint8.

    Pipeline: CIELAB -> XYZ (D65) -> linear RGB -> sRGB uint8.
    Inverse of ``_rgb_to_lab()``.
    """
    L = lab_array[:, 0]
    a = lab_array[:, 1]
    b = lab_array[:, 2]

    # LAB -> f values
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    # f values -> XYZ (inverse of the forward transform)
    epsilon = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    x = np.where(fx ** 3 > epsilon, fx ** 3, (116.0 * fx - 16.0) / kappa)
    y = np.where(L > kappa * epsilon, ((L + 16.0) / 116.0) ** 3, L / kappa)
    z = np.where(fz ** 3 > epsilon, fz ** 3, (116.0 * fz - 16.0) / kappa)

    # Denormalize by D65 white point
    d65 = np.array([0.95047, 1.00000, 1.08883])
    xyz = np.stack([x, y, z], axis=1) * d65  # (N, 3)

    # XYZ -> linear RGB (inverse of the sRGB D65 matrix)
    m_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252],
    ])
    linear_rgb = xyz @ m_inv.T  # (N, 3)

    # Clip to [0, 1] before gamma to avoid NaN from negative values
    linear_rgb = np.clip(linear_rgb, 0.0, 1.0)

    # Apply sRGB gamma companding
    srgb = np.where(
        linear_rgb > 0.0031308,
        1.055 * np.power(linear_rgb, 1.0 / 2.4) - 0.055,
        12.92 * linear_rgb,
    )

    # Clamp and convert to uint8
    srgb = np.clip(srgb * 255.0, 0.0, 255.0)
    return np.round(srgb).astype(np.uint8)


def _rgb_to_hsv_arrays(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert RGB uint8 array (H,W,3) to hue (0-360), saturation (0-1), value (0-1) arrays.

    Parameters
    ----------
    rgb : np.ndarray of shape (H, W, 3), dtype uint8

    Returns
    -------
    hue : np.ndarray (H, W) float64, degrees 0-360
    sat : np.ndarray (H, W) float64, 0-1
    val : np.ndarray (H, W) float64, 0-1
    """
    rgb_f = rgb.astype(np.float64) / 255.0

    cmax = rgb_f.max(axis=2)
    cmin = rgb_f.min(axis=2)
    delta = cmax - cmin

    hue = np.zeros_like(cmax)
    r, g, b = rgb_f[:, :, 0], rgb_f[:, :, 1], rgb_f[:, :, 2]

    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (delta > 0) & ~mask_r & ~mask_g

    hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6.0)
    hue[mask_g] = 60.0 * ((b[mask_g] - r[mask_g]) / delta[mask_g] + 2.0)
    hue[mask_b] = 60.0 * ((r[mask_b] - g[mask_b]) / delta[mask_b] + 4.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        sat = np.where(cmax > 0, delta / cmax, 0.0)

    return hue, sat, cmax


def _shift_masked_pixels(arr: np.ndarray, mask: np.ndarray, ref_lab: np.ndarray, strength: float) -> bool:
    """Shift pixels identified by mask toward ref_lab in LAB space.

    Extracts RGB pixels from *arr* at positions where *mask* is True,
    converts to LAB, blends toward *ref_lab* by *strength*, converts
    back, and writes the result into *arr* in-place.

    Parameters
    ----------
    arr : np.ndarray (H, W, 4) uint8 — the RGBA image array (modified in-place)
    mask : np.ndarray (H, W) bool — which pixels to shift
    ref_lab : np.ndarray (3,) — target LAB color to shift toward
    strength : float in [0, 1] — 0 = no change, 1 = full shift

    Returns
    -------
    bool : True if any pixels were modified
    """
    if not mask.any():
        return False
    px_rgb = arr[:, :, :3][mask].astype(np.float64)
    px_lab = _rgb_to_lab(px_rgb)
    shift = (ref_lab[np.newaxis, :] - px_lab) * strength
    shifted_lab = px_lab + shift
    shifted_rgb = _lab_to_rgb(shifted_lab)
    arr[:, :, :3][mask] = shifted_rgb
    return True


# Modifier x-offset ranges for each animation (from Tile.tsx modifier definitions).
# Used by the conservative init to estimate which columns each animation uses.
_ANIM_COL_OFFSETS: dict[str, tuple[int, int]] = {
    "Sea": (-1, 3),             # AreaModifiers
    "DeepSea": (-1, 3),         # AreaModifiers
    "Beach": (-3, 3),           # AreaModifiers + area decorators (x: -3 to 3)
    "River": (-3, 3),           # RiverModifiers
    "Pier": (0, 6),             # Pier-specific modifiers
    "StormCloud": (-1, 2),      # StormCloud modifiers
    "Lightning": (0, 0),        # Horizontal only
    "LightningV": (0, 0),       # Vertical only
    "RailBridge": (0, 2),       # Bridge modifiers
    "Computer": (0, 0),         # No modifiers
    "Teleporter": (0, 0),       # No modifiers
    "FloatingWaterEdge": (0, 3),  # FWE modifiers
    "Campsite": (0, 0),         # Horizontal
    "Reef": (0, 3),             # With variants
    "GasBubbles": (0, 0),       # Horizontal
    "Island": (0, 4),           # With variants
    "Iceberg/Weeds": (0, 3),    # With variants
    # FloatingEdge border animations
    "FE_Waterfall": (-1, 1),     # cols 8-10 (base_col=9, offsets -1 to +1)
    "FE_WallDecorA": (0, 1),     # cols 9-10 (base_col=9, offsets 0 to +1)
    "FE_WallDecorB": (0, 1),     # cols 9-10
    "FE_AreaDecor": (0, 1),      # cols 9-10
}


def _init_anim_frame_set_conservative():
    """Initialize animation frame set using estimated column ranges.

    Used by tests that don't have a real atlas available. Uses per-animation
    column offset ranges to approximate which (col, row) pairs are animation
    frames, avoiding false positives from overlapping row ranges.
    """
    global _anim_frame_set
    anim_frames: set[tuple[int, int]] = set()
    for entry in ANIMATED_TILES:
        name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
        min_x, max_x = _ANIM_COL_OFFSETS.get(name, (-3, 6))
        if horizontal:
            for i in range(1, frames):
                anim_frames.add((base_col + i * offset, base_row))
        else:
            block_start = base_row + block_start_delta
            for row_delta in range(offset):
                src_row = block_start + row_delta
                for col_offset in range(min_x, max_x + 1):
                    col = base_col + col_offset
                    if 0 <= col < ATLAS_COLS:
                        for i in range(1, frames):
                            anim_frames.add((col, src_row + i * offset))
    _anim_frame_set = anim_frames
    # Also build the animation cell map for metadata tagging
    _build_anim_cell_map_conservative()


# Pre-computed mapping: (col, row) -> (anim_name, frame_idx, cell_idx)
# Built by _build_anim_cell_map() for ALL animation cells (base + non-base).
_anim_cell_map: dict[tuple[int, int], tuple[str, int, int]] | None = None


def _build_anim_cell_map_conservative() -> dict[tuple[int, int], tuple[str, int, int]]:
    """Build animation cell metadata map using estimated column ranges.

    Returns a dict mapping (col, row) -> (anim_name, frame_idx, cell_idx)
    for ALL animation cells (base frame + non-base frames).
    Used by tests that don't have a real atlas available.
    """
    global _anim_cell_map
    result: dict[tuple[int, int], tuple[str, int, int]] = {}
    for entry in ANIMATED_TILES:
        name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
        min_x, max_x = _ANIM_COL_OFFSETS.get(name, (-3, 6))
        if horizontal:
            for i in range(frames):
                pos = (base_col + i * offset, base_row)
                if pos not in result:
                    result[pos] = (name, i, 0)
        else:
            block_start = base_row + block_start_delta
            for i in range(frames):
                cell_idx = 0
                for row_delta in range(abs(offset)):
                    src_row = block_start + row_delta + i * offset
                    for col_offset in range(min_x, max_x + 1):
                        col = base_col + col_offset
                        if 0 <= col < ATLAS_COLS:
                            pos = (col, src_row)
                            if pos not in result:
                                result[pos] = (name, i, cell_idx)
                            cell_idx += 1
    _anim_cell_map = result
    return result


def get_anim_cell_info(col: int, row: int) -> tuple[str, int, int] | None:
    """Return (anim_name, frame_idx, cell_idx) for an animation cell, or None."""
    global _anim_cell_map
    if _anim_cell_map is None:
        return None
    return _anim_cell_map.get((col, row))


def _partition_cells_for_batching(
    cells: list[dict],
) -> tuple[list[dict], dict[str, dict[int, list[dict]]], int]:
    """Split cells into static cells and animation cells grouped by frame.

    Animation cells are grouped by ``anim_name`` and ``anim_frame_idx`` and
    sorted by ``anim_cell_idx`` so animation batch rows stay aligned across
    frames, even if some cells are missing from a later frame.
    """
    static_cells: list[dict] = []
    anim_cells: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    excluded = 0

    for cell in cells:
        anim_name = cell.get("anim_name")
        if anim_name is not None:
            excluded += 1
            frame_idx = cell.get("anim_frame_idx")
            if frame_idx is not None:
                anim_cells[anim_name][frame_idx].append(cell)
            continue

        if cell.get("is_anim_frame"):
            excluded += 1
            continue

        static_cells.append(cell)

    for frames in anim_cells.values():
        for frame_cells in frames.values():
            frame_cells.sort(
                key=lambda cell: (
                    cell.get("anim_cell_idx") if cell.get("anim_cell_idx") is not None else float("inf"),
                    cell["row"],
                    cell["col"],
                ),
            )

    return static_cells, anim_cells, excluded


def is_animation_frame(col: int, row: int) -> bool:
    """Return True if this cell belongs to a non-base animation frame.

    Only non-base frames are marked here. Base animation cells are tracked via
    ``anim_name`` / ``anim_frame_idx`` metadata and are also excluded from the
    terrain-type batches, but they remain part of animation-aware batching.

    Uses per-(col, row) tracking computed from the actual atlas to avoid
    false positives where different tile types share atlas rows.
    """
    global _anim_frame_set
    if _anim_frame_set is None:
        raise RuntimeError("compute_anim_frame_set() must be called before is_animation_frame()")
    return (col, row) in _anim_frame_set

