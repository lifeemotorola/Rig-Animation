# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - an advanced human rig + animation toolkit for Blender 5.2.

The add-on is a Blender extension: it is imported as
``bl_ext.<repo>.apex_rig`` and therefore must not define ``bl_info``.
"""
from __future__ import annotations

import importlib

import bpy

from . import const

__version__ = const.VERSION_STRING
__package_id__ = "apex_rig"

__APEX_MODULES = (
    "utils",
    "widgets",
    "skin",
    "skin_body",
    "deform",
    "poses",
    "face",
    "live",
    "ui_icons",
    "face_icons",
    "animation",
    "mocap",
    "export",
    "rig",
    "properties",
    "operators",
    "panels",
)

_loaded = []


def _reload_modules():
    """Make `Reload Scripts` (F8) pick up changes while developing."""
    global _loaded
    for name in _APEX_MODULES:
        full = f"{__name__}.{name}"
        if full in __import__("sys").modules:
            importlib.reload(__import__("sys").modules[full])
    _loaded = []


def register():
    from . import properties, operators, panels

    properties.register()
    operators.register()
    panels.register()
    try:
        from . import ui_icons
        ui_icons.clear()          # fresh preview cache after a reload
    except Exception:
        pass
    utils_mod = __import__(f"{__name__}.utils", fromlist=["log"])
    utils_mod.log.info("%s %s registered", const.ADDON_NAME, const.VERSION_STRING)

    # keep the rig usable right after a file is opened
    if _register_handlers not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_register_handlers)


def unregister():
    from . import operators, panels, properties

    if _register_handlers in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_register_handlers)
    panels.unregister()
    operators.unregister()
    properties.unregister()
    try:
        from . import ui_icons
        ui_icons.clear()
    except Exception:
        pass


def _register_handlers(_dummy=None):
    """Post-load hook: nothing to rebuild, but keep the UI state sane."""
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass
