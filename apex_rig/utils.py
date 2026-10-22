# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - shared utilities.

Small, dependency-free helpers used across the add-on.  Every Blender version
quirk (legacy F-Curves vs. 5.x slotted actions, NLA slots, drivers) is isolated
here so the feature modules stay readable.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Iterable, Sequence

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

log = logging.getLogger("apex_rig")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[Apex] %(levelname)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

BL_VERSION = bpy.app.version
IS_5X = BL_VERSION >= (5, 0, 0)

MIRROR_X = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mirror_name(name: str) -> str:
    if name.endswith(".L"):
        return name[:-2] + ".R"
    if name.endswith(".R"):
        return name[:-2] + ".L"
    if name.endswith("_L"):
        return name[:-2] + "_R"
    if name.endswith("_R"):
        return name[:-2] + "_L"
    if name.endswith(".l"):
        return name[:-2] + ".r"
    if name.endswith(".r"):
        return name[:-2] + ".l"
    return name


def side_of(name: str) -> str:
    if name.endswith((".L", "_L", ".l", "left")):
        return "L"
    if name.endswith((".R", "_R", ".r", "right")):
        return "R"
    return "C"


def ensure_object_mode() -> None:
    obj = bpy.context.view_layer.objects.active
    if obj and obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def set_active(obj) -> None:
    if bpy.context.view_layer.objects.active is not obj:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj


def select_only(objs: Iterable) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    first = None
    for ob in objs:
        ob.select_set(True)
        if first is None:
            first = ob
    if first is not None:
        bpy.context.view_layer.objects.active = first


def unique_name(base: str, collection=None) -> str:
    coll = collection if collection is not None else bpy.data.objects
    if base not in coll:
        return base
    i = 1
    while f"{base}.{i:03d}" in coll:
        i += 1
    return f"{base}.{i:03d}"


def safe_remove(obj) -> None:
    if obj is None:
        return
    try:
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Could not remove %s: %s", obj, exc)


def to_json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def from_json(text: str, default=None):
    try:
        return json.loads(text)
    except Exception:
        return default if default is not None else {}


# ---------------------------------------------------------------------------
# Object / data lookups
# ---------------------------------------------------------------------------
def is_apex_rig(obj) -> bool:
    from .const import RIG_ID_KEY

    return (
        obj is not None
        and obj.type == "ARMATURE"
        and bool(obj.get(RIG_ID_KEY, False))
        and obj.data is not None
    )


def active_armature(require_apex: bool = False):
    ob = bpy.context.view_layer.objects.active
    if ob is not None and ob.type == "ARMATURE":
        if not require_apex or is_apex_rig(ob):
            return ob
    if require_apex:
        for o in bpy.context.selected_objects:
            if is_apex_rig(o):
                return o
        for o in bpy.data.objects:
            if is_apex_rig(o):
                return o
    return None


# ---------------------------------------------------------------------------
# Slotted actions / F-Curves  (Blender 4.4+ layered actions, required in 5.x)
# ---------------------------------------------------------------------------
def ensure_slot(action, id_type: str = "OBJECT", name: str | None = None):
    """Return the first matching slot, creating one if the action is empty."""
    for slot in action.slots:
        if slot.target_id_type == id_type:
            return slot
    return action.slots.new(id_type=id_type, name=name or "Object")


def action_channelbag(action, slot=None, create: bool = True):
    """Get the channelbag for *slot* (creating layer / strip / bag if needed)."""
    if action is None:
        return None
    if slot is None:
        slot = action.slots[0] if len(action.slots) else (ensure_slot(action) if create else None)
    if slot is None:
        return None
    if len(action.layers) == 0:
        if not create:
            return None
        layer = action.layers.new("Apex Base")
        layer.strips.new(type="KEYFRAME")
    layer = action.layers[0]
    strip = None
    for s in layer.strips:
        if s.type == "KEYFRAME":
            strip = s
            break
    if strip is None:
        if not create:
            return None
        strip = layer.strips.new(type="KEYFRAME")
    try:
        return strip.channelbag(slot, ensure=create)
    except TypeError:  # Blender < 4.4 fallback
        return strip.channelbag(slot)
    except Exception as exc:
        log.warning("channelbag lookup failed: %s", exc)
        return None


def action_fcurves(action, slot=None) -> list:
    """All F-Curves of an action (first channelbag), version tolerant."""
    if action is None:
        return []
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        try:
            return list(legacy)
        except Exception:
            pass
    bag = action_channelbag(action, slot, create=False)
    return list(bag.fcurves) if bag is not None else []


def get_fcurve(action, slot, data_path: str, index: int, create: bool = True):
    bag = action_channelbag(action, slot, create=create)
    if bag is None:
        return None
    for fc in bag.fcurves:
        if fc.data_path == data_path and fc.array_index == index:
            return fc
    if not create:
        return None
    return bag.fcurves.new(data_path, index=index)


def write_curve(action, slot, data_path: str, index: int, frames: Sequence[float],
                values: Sequence[float], interpolation: str = "BEZIER") -> None:
    """Bulk-write a curve using foreach_set (fast path for baked motion)."""
    fc = get_fcurve(action, slot, data_path, index)
    n = min(len(frames), len(values))
    if n == 0:
        return
    if len(fc.keyframe_points):
        fc.keyframe_points.clear()
    fc.keyframe_points.add(n)
    co = [0.0] * (2 * n)
    co[0::2] = [float(f) for f in frames[:n]]
    co[1::2] = [float(v) for v in values[:n]]
    fc.keyframe_points.foreach_set("co", co)
    for kp in fc.keyframe_points:
        kp.interpolation = interpolation
    fc.update()


def new_action_for(owner, name: str):
    """Create an action, assign it to *owner* and return (action, slot)."""
    action = bpy.data.actions.new(unique_name(name, bpy.data.actions))
    action.use_fake_user = True
    if owner.animation_data is None:
        owner.animation_data_create()
    owner.animation_data.action = action
    slot = ensure_slot(action, id_type="OBJECT", name=owner.name)
    owner.animation_data.action_slot = slot
    return action, slot


def current_action(owner):
    ad = getattr(owner, "animation_data", None)
    return ad.action if ad else None


def action_range(action) -> tuple[float, float]:
    if action is None:
        return (1.0, 1.0)
    try:
        r = action.frame_range
        return (float(r[0]), float(r[1]))
    except Exception:
        pass
    curves = action_fcurves(action)
    if not curves:
        return (1.0, 1.0)
    starts = [fc.range()[0] for fc in curves if len(fc.keyframe_points)]
    ends = [fc.range()[1] for fc in curves if len(fc.keyframe_points)]
    if not starts:
        return (1.0, 1.0)
    return (min(starts), max(ends))


# ---------------------------------------------------------------------------
# NLA
# ---------------------------------------------------------------------------
def add_nla_strip(owner, action, slot, name: str, blend: str = "REPLACE",
                  start: float | None = None, track_name: str | None = None,
                  mute: bool = False):
    """Push an action on its own NLA track and return the strip."""
    ad = owner.animation_data or owner.animation_data_create()
    tr = ad.nla_tracks.new()
    tr.name = unique_name(track_name or name, ad.nla_tracks)
    if action is None:
        raise ValueError("add_nla_strip requires an action")
    if slot is None:
        slot = action.slots[0] if len(action.slots) else ensure_slot(action)
    if start is None:
        start = action_range(action)[0]
    strip = tr.strips.new(name=name, start=int(round(start)), action=action)
    try:
        strip.action_slot = slot
    except Exception:
        pass
    strip.blend_type = blend
    strip.extrapolation = "HOLD" if blend == "REPLACE" else "NOTHING"
    strip.use_auto_blend = False
    tr.mute = mute
    return strip


def find_nla_track(owner, name: str):
    ad = getattr(owner, "animation_data", None)
    if ad:
        for tr in ad.nla_tracks:
            if tr.name == name:
                return tr
    return None


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------
def add_driver(owner, path: str, index, expression: str, variables=()):
    """Create a scripted driver with simple-expression-safe variables.

    variables: iterable of (name, id_data, data_path)
    Expressions must stay within Blender's "simple expression" subset so they
    evaluate even when auto-run Python scripts are disabled.
    """
    fc = owner.driver_add(path, index) if index is not None else owner.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    # drop pre-existing variables
    for var in list(drv.variables):
        drv.variables.remove(var)
    for vname, id_data, data_path in variables:
        var = drv.variables.new()
        var.name = vname
        var.type = "SINGLE_PROP"
        tgt = var.targets[0]
        tgt.id = id_data
        tgt.data_path = data_path
    drv.expression = expression
    return fc


def prop_bone_path(bone_name: str, prop_name: str) -> str:
    return f'pose.bones["{bone_name}"]["{prop_name}"]'


def drive_from_prop(owner, path: str, index, arm_obj, prop_bone: str,
                    prop_name: str, expression: str = "c"):
    """Drive owner.path[index] from a property stored on a pose bone."""
    return add_driver(owner, path, index, expression,
                      [("c", arm_obj, prop_bone_path(prop_bone, prop_name))])


def clear_drivers(owner) -> int:
    count = 0
    ad = getattr(owner, "animation_data", None)
    if ad is None:
        return 0
    for fc in list(ad.drivers):
        if fc.driver is not None:
            ad.drivers.remove(fc)
            count += 1
    return count


# ---------------------------------------------------------------------------
# ID properties with UI metadata
# ---------------------------------------------------------------------------
def set_idprop(owner, name: str, value, *, minv=None, maxv=None, soft_min=None,
               soft_max=None, description=None, subtype=None, step=None) -> None:
    owner[name] = value
    try:
        ui = owner.id_properties_ui(name)
        kwargs = {}
        if minv is not None:
            kwargs["min"] = minv
        if maxv is not None:
            kwargs["max"] = maxv
        if soft_min is not None:
            kwargs["soft_min"] = soft_min
        if soft_max is not None:
            kwargs["soft_max"] = soft_max
        if description:
            kwargs["description"] = description
        if subtype:
            kwargs["subtype"] = subtype
        if step is not None:
            kwargs["step"] = step
        ui.update(**kwargs)
    except Exception as exc:  # pragma: no cover
        log.debug("id prop ui failed for %s: %s", name, exc)


# ---------------------------------------------------------------------------
# Pose helpers
# ---------------------------------------------------------------------------
def refresh(arm) -> None:
    """Re-evaluate drivers and constraints after a programmatic change.

    Blender only rebuilds driver relations when the ID is tagged; UI edits do
    this automatically but Python-side edits do not.
    """
    try:
        arm.update_tag()
    except Exception:
        pass
    bpy.context.view_layer.update()


def bone_depth(pb) -> int:
    depth = 0
    parent = pb.parent
    while parent is not None:
        depth += 1
        parent = parent.parent
    return depth


def pose_snapshot(arm, names: Iterable[str] | None = None) -> dict:
    data = {}
    for pb in arm.pose.bones:
        if names is not None and pb.name not in names:
            continue
        entry = {
            "mode": pb.rotation_mode,
            "location": list(pb.location),
            "scale": list(pb.scale),
        }
        if pb.rotation_mode == "QUATERNION":
            entry["rotation"] = list(pb.rotation_quaternion)
        elif pb.rotation_mode == "AXIS_ANGLE":
            entry["rotation"] = list(pb.rotation_axis_angle)
        else:
            entry["rotation"] = list(pb.rotation_euler)
        data[pb.name] = entry
    return data


def _rotation_from_entry(pb, entry):
    mode = entry.get("mode", "QUATERNION")
    rot = entry.get("rotation", [1, 0, 0, 0])
    if pb.rotation_mode == mode:
        return rot
    # convert between rotation representations
    if mode == "QUATERNION":
        q = Quaternion(rot)
        if pb.rotation_mode == "AXIS_ANGLE":
            axis, angle = q.to_axis_angle()
            return [angle, axis.x, axis.y, axis.z]
        return list(q.to_euler(pb.rotation_mode))
    if mode == "AXIS_ANGLE":
        q = Quaternion((rot[1], rot[2], rot[3]), rot[0])
    else:
        q = Euler(rot, mode).to_quaternion()
    if pb.rotation_mode == "QUATERNION":
        return list(q)
    if pb.rotation_mode == "AXIS_ANGLE":
        axis, angle = q.to_axis_angle()
        return [angle, axis.x, axis.y, axis.z]
    return list(q.to_euler(pb.rotation_mode))


def pose_apply(arm, data: dict, update: bool = True) -> None:
    for name, entry in data.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        pb.location = entry.get("location", (0, 0, 0))
        pb.scale = entry.get("scale", (1, 1, 1))
        rot = _rotation_from_entry(pb, entry)
        if pb.rotation_mode == "QUATERNION":
            pb.rotation_quaternion = rot
        elif pb.rotation_mode == "AXIS_ANGLE":
            pb.rotation_axis_angle = rot
        else:
            pb.rotation_euler = rot
    if update:
        bpy.context.view_layer.update()


def clear_pose(arm, prop_defaults: bool = False) -> None:
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    if prop_defaults:
        from . import rig as rig_module
        rig_module.reset_properties(arm)
    bpy.context.view_layer.update()


def mirror_pose(arm) -> None:
    """Mirror the current pose across the YZ plane.

    Bone *matrices* are reflected rather than channel values, so the result is
    exact for any bone roll, constraint setup or rotation mode.
    """
    snapshot = {pb.name: pb.matrix.copy() for pb in arm.pose.bones}
    targets = []
    for pb in arm.pose.bones:
        dst = arm.pose.bones.get(mirror_name(pb.name))
        if dst is None:
            continue
        targets.append((dst, MIRROR_X @ snapshot[pb.name] @ MIRROR_X))
    targets.sort(key=lambda item: bone_depth(item[0]))
    for dst, mat in targets:
        dst.matrix = mat
        bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def swap_side_props(arm, prop_names: Sequence[str]) -> None:
    for name in prop_names:
        lname = name.replace(".L", ".L")
        left = name + ("" if name.endswith((".L", ".R")) else "")
        if left.endswith(".L"):
            right = left[:-2] + ".R"
            a = arm.pose.bones["root"].get(left)
            b = arm.pose.bones["root"].get(right)
            if a is None or b is None:
                continue
            arm.pose.bones["root"][left] = b
            arm.pose.bones["root"][right] = a


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------
def rig_collection(arm):
    """Return the bone-collection tagged as the rig's control set, if any."""
    for coll in arm.data.collections:
        if coll.name in ("Controllers", "APEX Controllers", "CTRL"):
            return coll
    return arm.data.collections[0] if arm.data.collections else None


def meshes_of_armature(arm) -> list:
    result = []
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if ob.parent is arm:
            result.append(ob)
            continue
        for mod in ob.modifiers:
            if mod.type == "ARMATURE" and mod.object is arm:
                result.append(ob)
                break
    return result


def all_armature_modifiers(arm) -> list:
    mods = []
    for ob in meshes_of_armature(arm):
        for mod in ob.modifiers:
            if mod.type == "ARMATURE" and mod.object is arm:
                mods.append((ob, mod))
    return mods


def get_text(name: str, create: bool = False):
    text = bpy.data.texts.get(name)
    if text is None and create:
        text = bpy.data.texts.new(name)
    return text


def read_text_json(name: str, default):
    text = get_text(name)
    if text is None or not text.as_string().strip():
        return default
    return from_json(text.as_string(), default)


def write_text_json(name: str, data) -> None:
    text = get_text(name, create=True)
    text.clear()
    text.write(to_json(data))


def fmt_float(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"
