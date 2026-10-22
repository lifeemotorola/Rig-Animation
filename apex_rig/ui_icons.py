# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - preview thumbnails for picture buttons.

PNG previews live in ``<addon>/previews`` and are loaded through Blender's
preview collection, which gives every image an ``icon_id`` usable by
``UILayout.operator(icon_value=...)``.

Head-less Blender (``-b``) does not allocate GL icons, so ``icon_id`` is 0
there; every panel therefore falls back to a text button when the id is 0.
"""
from __future__ import annotations

import atexit
import os

import bpy

_previews = None
_loaded = {}
_missing = object()


def preview_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")


def _collection():
    global _previews
    if _previews is None:
        try:
            import bpy.utils.previews

            _previews = bpy.utils.previews.new()
        except Exception:
            _previews = False
    return _previews or None


def preview_path(kind: str, key: str) -> str:
    return os.path.join(preview_dir(), f"{kind}_{key}.png")


def icon_id(kind: str, key: str) -> int:
    """Cached icon id for ``previews/<kind>_<key>.png`` (0 when unavailable)."""
    cache_key = f"{kind}_{key}"
    if cache_key in _loaded:
        value = _loaded[cache_key]
        return 0 if value is _missing else value
    collection = _collection()
    path = preview_path(kind, key)
    if collection is None or not os.path.exists(path):
        _loaded[cache_key] = _missing
        return 0
    try:
        entry = collection.load(cache_key, path, "IMAGE")
        value = getattr(entry, "icon_id", 0) or 0
    except Exception:
        value = 0
    _loaded[cache_key] = value if value else _missing
    return value


def has_preview(kind: str, key: str) -> bool:
    return os.path.exists(preview_path(kind, key))


def clear():
    global _previews
    if _previews:
        try:
            bpy.utils.previews.remove(_previews)
        except Exception:
            pass
    _previews = None
    _loaded.clear()


def available_kinds() -> list[str]:
    folder = preview_dir()
    if not os.path.isdir(folder):
        return []
    kinds = set()
    for name in os.listdir(folder):
        if name.endswith(".png") and "_" in name:
            kinds.add(name.split("_", 1)[0])
    return sorted(kinds)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------
def picture_button(layout, operator: str, kind: str, key: str, label: str,
                   props: dict | None = None, columns: int = 1):
    """One clickable thumbnail with a caption (falls back to a text button)."""
    icon = icon_id(kind, key)
    column = layout.column(align=True)
    column.scale_y = 1.0
    if icon:
        row = column.row(align=True)
        op = row.operator(operator, text="", icon_value=icon)
        if props:
            for prop_name, value in props.items():
                setattr(op, prop_name, value)
        caption = column.row(align=True)
        caption.scale_y = 0.8
        caption.label(text=label)
    else:
        op = column.operator(operator, text=label, icon="IMAGE_DATA")
        if props:
            for prop_name, value in props.items():
                setattr(op, prop_name, value)
    return column


def picture_grid(layout, operator: str, items, kind: str, columns: int = 4,
                 props_for=None):
    """Grid of picture buttons from ``[(key, label), ...]``."""
    grid = layout.grid_flow(row_major=True, columns=columns, align=True,
                            even_columns=True, even_rows=True)
    for key, label in items:
        props = props_for(key) if props_for else None
        picture_button(grid, operator, kind, key, label, props, columns)
    return grid


atexit.register(clear)
