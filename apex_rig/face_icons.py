# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - picture buttons for the facial expression library."""
from __future__ import annotations

import os

from . import ui_icons


def _dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")


def icon(kind: str, key: str) -> int:
    return ui_icons.icon_id(f"face_{kind}", key)


def picture_grid(layout, kind: str, keys, columns: int = 4,
                 operator: str = "apex.live_expression", **props) -> int:
    """Draw a grid of expression thumbnails (text buttons when headless)."""
    from . import face

    keys = list(keys)
    for start in range(0, len(keys), columns):
        row = layout.row(align=True)
        for key in keys[start:start + columns]:
            label = face.EXPRESSIONS[key][0] if key in face.EXPRESSIONS else key
            icon_value = icon(kind, key)
            if icon_value:
                op = row.operator(operator, text="", icon_value=icon_value,
                                  emboss=True)
            else:
                op = row.operator(operator, text=label)
            op.expression = key
    return len(keys)
