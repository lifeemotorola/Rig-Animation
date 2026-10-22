# SPDX-License-Identifier: GPL-3.0-or-later
"""Apex Rig & Motion - rig builder and runtime API.

``build_rig`` turns a :class:`~apex_rig.proportions.RigOptions` into a fully
constrained, colour-coded and widget-driven human armature.  The :class:`Rig`
wrapper is the stable runtime interface used by every other module (rename
safe, side aware).
"""
from __future__ import annotations

import json
import math
from typing import Iterable

import bpy
from mathutils import Matrix, Vector

from . import utils, widgets
from .const import (
    BONE_COLLECTIONS,
    COLOR,
    CURL_FACTORS,
    NAME_MAP_KEY,
    PROPS,
    PROPS_BONE,
    RIG_ID_KEY,
    RIG_NAME,
    RIG_VERSION_KEY,
    SPREAD_FACTORS,
    VERSION_STRING,
)
from .proportions import FWD, SIDE, BoneSpec, HumanProportions, RigOptions

DEG = math.pi / 180.0

# constraint names (stable handles for later edits)
CON_IK = "APEX IK"
CON_POLE = "APEX Pole"
CON_FOLLOW = "APEX IK Follow"
CON_TWIST = "APEX Twist"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
class BuildResult:
    def __init__(self, arm, proportions: HumanProportions):
        self.arm = arm
        self.proportions = proportions


def _ensure_collection_name(arm_data, name: str):
    coll = arm_data.collections.get(name)
    return coll if coll is not None else arm_data.collections.new(name)


def _create_armature(context, name: str):
    data = bpy.data.armatures.new(utils.unique_name(f"{name}-Data", bpy.data.armatures))
    obj = bpy.data.objects.new(utils.unique_name(name), data)
    coll = bpy.context.collection or bpy.context.scene.collection
    coll.objects.link(obj)
    utils.set_active(obj)
    return obj


def _create_edit_bones(arm, specs: list[BoneSpec]) -> None:
    data = arm.data
    bpy.ops.object.mode_set(mode="EDIT")
    pending = list(specs)
    created = {}
    guard = 0
    while pending and guard < 1000:
        guard += 1
        remaining = []
        for spec in pending:
            if spec.parent and spec.parent not in created:
                remaining.append(spec)
                continue
            eb = data.edit_bones.new(spec.name)
            eb.head = spec.head
            eb.tail = spec.tail
            eb.use_deform = spec.deform
            eb.bbone_segments = max(1, int(spec.segments))
            eb.head_radius = max(1e-4, spec.radius)
            eb.tail_radius = max(1e-4, spec.radius_tail if spec.radius_tail else spec.radius)
            eb.envelope_distance = max(1e-4, spec.radius * 0.8)
            if spec.parent:
                eb.parent = created[spec.parent]
                eb.use_connect = bool(spec.connect)
            direction = (spec.tail - spec.head)
            if direction.length > 1e-6:
                direction.normalize()
                if spec.roll_x is not None:
                    z_axis = spec.roll_x.cross(direction)
                    if z_axis.length > 1e-6:
                        eb.align_roll(z_axis)
                elif spec.roll_z is not None:
                    eb.align_roll(spec.roll_z)
            created[spec.name] = eb
        pending = remaining
    if pending:
        raise RuntimeError(f"Unresolved bone parents: {[s.name for s in pending]}")
    bpy.ops.object.mode_set(mode="OBJECT")


def _setup_collections(arm, specs: list[BoneSpec]) -> None:
    data = arm.data
    for name in BONE_COLLECTIONS:
        _ensure_collection_name(data, name)
    # remove the implicit "Bones" collection created by Blender if unused
    for spec in specs:
        coll = _ensure_collection_name(data, spec.collection)
        bone = data.bones.get(spec.name)
        if bone is not None:
            coll.assign(bone)
    for name, (visible, _color) in BONE_COLLECTIONS.items():
        coll = data.collections.get(name)
        if coll is not None:
            coll.is_visible = visible
    default = data.collections.get("Bones")
    if default is not None and len(default.bones) == 0:
        try:
            data.collections.remove(default)
        except Exception:
            pass


def _setup_colors(arm, specs: list[BoneSpec]) -> None:
    for spec in specs:
        bone = arm.data.bones.get(spec.name)
        if bone is None:
            continue
        idx = COLOR.get(spec.color, COLOR["CENTER"])
        try:
            bone.color.palette = f"THEME{idx:02d}"
        except Exception:
            pass


def _setup_widgets(arm, specs: list[BoneSpec]) -> None:
    for spec in specs:
        if not spec.widget:
            continue
        widgets.assign_shape(arm, spec.name, spec.widget, spec.widget_scale,
                             rotation=spec.widget_rotation)
    widgets.hide_widget_collection(bpy.context.scene)


def _setup_rotation_modes(arm, specs: list[BoneSpec]) -> None:
    for spec in specs:
        pb = arm.pose.bones.get(spec.name)
        if pb is None:
            continue
        if any(part in spec.name for part in ("f_index", "f_middle", "f_ring",
                                              "f_pinky", "thumb")):
            pb.rotation_mode = "XYZ"
        else:
            pb.rotation_mode = "QUATERNION"


def _create_props(arm, opts: RigOptions) -> None:
    pb = arm.pose.bones.get(PROPS_BONE) or (arm.pose.bones[0] if len(arm.pose.bones) else None)
    if pb is None:
        return
    for name, (default, mn, mx, smn, smx, desc) in PROPS.items():
        value = float(default)
        if name == "ik_arm.L":
            value = 1.0 if opts.ik_arms else 0.0
        elif name == "ik_arm.R":
            value = 1.0 if opts.ik_arms else 0.0
        elif name == "ik_leg.L":
            value = 1.0 if opts.ik_legs else 0.0
        elif name == "ik_leg.R":
            value = 1.0 if opts.ik_legs else 0.0
        utils.set_idprop(pb, name, value, minv=mn, maxv=mx, soft_min=smn,
                         soft_max=smx, description=desc)
    arm[PROPS_BONE + "_bone"] = pb.name


def _prop(arm, name: str, default=0.0) -> float:
    props_name = arm.get(PROPS_BONE + "_bone", PROPS_BONE)
    pb = arm.pose.bones.get(props_name)
    if pb is None or name not in pb.keys():
        return float(default)
    return float(pb[name])


def _set_prop(arm, name: str, value: float) -> None:
    props_name = arm.get(PROPS_BONE + "_bone", PROPS_BONE)
    pb = arm.pose.bones.get(props_name)
    if pb is not None:
        pb[name] = float(value)


def _make_ik(arm, side: str, props: dict, specs_by_name: dict, opts: RigOptions) -> None:
    # ---- arm ---------------------------------------------------------------
    forearm = arm.pose.bones.get(f"forearm.{side}")
    if forearm is not None:
        con = forearm.constraints.new("IK")
        con.name = CON_IK + " Arm"
        con.target = arm
        con.subtarget = f"hand_ik.{side}"
        con.chain_count = 2
        con.use_stretch = True
        con.use_tail = True  # chain resolves to the target head (validated in 5.2)
        if opts.pole_targets:
            con.pole_target = arm
            con.pole_subtarget = f"elbow_pole.{side}"
            con.pole_angle = 0.0
        props.setdefault("ik_constraints", []).append(con)

    hand = arm.pose.bones.get(f"hand.{side}")
    if hand is not None:
        con = hand.constraints.new("COPY_ROTATION")
        con.name = CON_FOLLOW + " Hand"
        con.target = arm
        con.subtarget = f"hand_ik.{side}"
        con.target_space = "WORLD"
        con.owner_space = "WORLD"
        con.mix_mode = "REPLACE"
        con.influence = 0.0
        props.setdefault("follow_constraints", []).append(con)

    # ---- leg ---------------------------------------------------------------
    shin = arm.pose.bones.get(f"shin.{side}")
    if shin is not None:
        con = shin.constraints.new("IK")
        con.name = CON_IK + " Leg"
        con.target = arm
        con.subtarget = f"foot_ik.{side}"
        con.chain_count = 2
        con.use_stretch = True
        con.use_tail = True  # chain resolves to the target head (validated in 5.2)
        if opts.pole_targets:
            con.pole_target = arm
            con.pole_subtarget = f"knee_pole.{side}"
            con.pole_angle = 0.0
        props.setdefault("ik_constraints", []).append(con)

    for bone_name, ctl in ((f"foot.{side}", f"foot_ik.{side}"),
                           (f"toe.{side}", f"toe_ik.{side}")):
        pb = arm.pose.bones.get(bone_name)
        if pb is None:
            continue
        con = pb.constraints.new("COPY_ROTATION")
        con.name = CON_FOLLOW + " " + bone_name
        con.target = arm
        con.subtarget = ctl
        con.target_space = "WORLD"
        con.owner_space = "WORLD"
        con.mix_mode = "REPLACE"
        con.influence = 0.0
        props.setdefault("follow_constraints", []).append(con)


def _make_twists(arm, side: str) -> None:
    hand = arm.pose.bones.get(f"hand.{side}")
    if hand is None:
        return
    for name, factor in ((f"upper_arm_twist.{side}", 0.35),
                         (f"forearm_twist.{side}", 0.65)):
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        con = pb.constraints.new("COPY_ROTATION")
        con.name = CON_TWIST
        con.target = arm
        con.subtarget = f"hand.{side}"
        con.target_space = "LOCAL"
        con.owner_space = "LOCAL"
        con.use_x = False
        con.use_y = True
        con.use_z = False
        con.mix_mode = "REPLACE"
        con.influence = 0.0
        con["apex_twist_factor"] = factor


def _setup_ik_limits(arm) -> None:
    """Anatomical IK limits: elbows and knees are hinges.

    Chain-root bones also get ``lock_ik_*`` so the solver can never translate
    them (which it otherwise does by rotating their parent, silently moving the
    hips/spine when a limb is over-extended).
    """
    for side in SIDE:
        for root_bone in (f"upper_arm.{side}", f"thigh.{side}"):
            pb = arm.pose.bones.get(root_bone)
            if pb is not None:
                pb.use_ik_linear_control = False
                pb.ik_stretch = 0.0
    for side in SIDE:
        for name, axis_min, axis_max in (
            (f"upper_arm.{side}", -2.6, 1.2),
            (f"forearm.{side}", 0.02, 2.45),
            (f"thigh.{side}", -1.9, 0.9),
            (f"shin.{side}", 0.02, 2.35),
        ):
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            pb.use_ik_limit_x = True
            pb.ik_min_x = axis_min
            pb.ik_max_x = axis_max
            # Soft stiffness (not hard limits) keeps the hinge plane stable while
            # still letting the pole target and the solver reach every target.
            pb.use_ik_limit_y = False
            pb.use_ik_limit_z = False
            pb.ik_stiffness_y = 0.75
            pb.ik_stiffness_z = 0.75


def _calibrate_pole(arm, side: str, limb: str, offset: Vector) -> float:
    """Find the pole angle that makes the joint point at its pole target.

    Returns the best angle in degrees.  Works on any proportion because it
    measures the solved pose instead of assuming an axis convention.
    """
    if limb == "arm":
        ctl, upper, lower, pole = (f"hand_ik.{side}", f"upper_arm.{side}",
                                   f"forearm.{side}", f"elbow_pole.{side}")
    else:
        ctl, upper, lower, pole = (f"foot_ik.{side}", f"thigh.{side}",
                                   f"shin.{side}", f"knee_pole.{side}")
    ik_con = None
    con_hint = CON_IK + (" Arm" if limb == "arm" else " Leg")
    for con in arm.pose.bones[lower].constraints:
        if con.type == "IK" and con.name == con_hint:
            ik_con = con
            break
    if ik_con is None or not ik_con.pole_target:
        return 0.0
    ctl_pb = arm.pose.bones.get(ctl)
    pole_pb = arm.pose.bones.get(pole)
    if ctl_pb is None or pole_pb is None:
        return 0.0

    old_influence = ik_con.influence
    old_matrix = ctl_pb.matrix.copy()
    ik_con.influence = 1.0
    moved = old_matrix.copy()
    moved.translation = moved.translation + offset
    ctl_pb.matrix = moved
    bpy.context.view_layer.update()

    best_angle, best_score = 0.0, -1e9
    for candidate in (0.0, 90.0, -90.0, 180.0, 45.0, -45.0, 135.0, -135.0):
        ik_con.pole_angle = candidate * DEG
        bpy.context.view_layer.update()
        joint = arm.pose.bones[upper].tail
        root = arm.pose.bones[upper].head
        tip = arm.pose.bones[lower].tail
        axis = tip - root
        if axis.length < 1e-6:
            continue
        closest = root + axis * utils.clamp((joint - root).dot(axis) / axis.length_squared,
                                            0.0, 1.0)
        v1 = joint - closest
        v2 = pole_pb.head - closest
        if v1.length < 1e-6 or v2.length < 1e-6:
            continue
        score = v1.normalized().dot(v2.normalized())
        utils.log.debug("pole %s/%s angle=%s score=%.3f", side, limb, candidate, score)
        if score > best_score:
            best_score, best_angle = score, candidate

    utils.log.debug("pole %s/%s -> best %s deg (score %.3f)", side, limb, best_angle, best_score)
    # restore
    ctl_pb.matrix = old_matrix
    ik_con.pole_angle = best_angle * DEG
    ik_con.influence = old_influence
    bpy.context.view_layer.update()
    return best_angle


def _setup_drivers(arm, opts: RigOptions) -> None:
    props_bone = arm.get(PROPS_BONE + "_bone", PROPS_BONE)

    def from_prop(obj, path, index, prop_name, expr="c"):
        utils.drive_from_prop(obj, path, index, arm, props_bone, prop_name, expr)

    for side in SIDE:
        # IK / FK blend
        for con in arm.pose.bones[f"forearm.{side}"].constraints:
            if con.type == "IK" and con.name == CON_IK + " Arm":
                from_prop(con, "influence", None, f"ik_arm.{side}")
        for con in arm.pose.bones[f"shin.{side}"].constraints:
            if con.type == "IK" and con.name == CON_IK + " Leg":
                from_prop(con, "influence", None, f"ik_leg.{side}")

        # follow constraints
        for pb in arm.pose.bones:
            for con in pb.constraints:
                if con.name.startswith(CON_FOLLOW) and con.type == "COPY_ROTATION":
                    if con.subtarget.endswith(f"hand_ik.{side}"):
                        from_prop(con, "influence", None, f"ik_arm.{side}")
                    elif con.subtarget.endswith(f"foot_ik.{side}") or \
                            con.subtarget.endswith(f"toe_ik.{side}"):
                        from_prop(con, "influence", None, f"ik_leg.{side}")

        # pole angle (stored in degrees for animator friendliness)
        if opts.pole_targets:
            for con in list(arm.pose.bones[f"forearm.{side}"].constraints) + \
                    list(arm.pose.bones[f"shin.{side}"].constraints):
                if con.type == "IK" and con.pole_target:
                    prop = (f"pole_angle_{'arm' if 'Arm' in con.name else 'leg'}.{side}")
                    from_prop(con, "pole_angle", None, prop, "c*0.017453292519943295")

        # stretch
        for name in (f"forearm.{side}", f"shin.{side}"):
            pb = arm.pose.bones.get(name)
            if pb is not None:
                from_prop(pb, "ik_stretch", None, "ik_stretch")

        # twists
        for name in (f"upper_arm_twist.{side}", f"forearm_twist.{side}"):
            pb = arm.pose.bones.get(name)
            if pb is None:
                continue
            for con in pb.constraints:
                if con.name == CON_TWIST:
                    factor = float(con.get("apex_twist_factor", 0.5))
                    from_prop(con, "influence", None, f"twist.{side}", f"c*{factor:.3f}")

        # fingers ---------------------------------------------------------
        finger_names = ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]
        for fname in finger_names:
            count = 3
            for i in range(1, count + 1):
                pb = arm.pose.bones.get(f"{fname}_{i:02d}.{side}")
                if pb is None:
                    continue
                curl = CURL_FACTORS.get(fname, (1.0, 1.0, 1.0))[i - 1]
                if fname == "thumb":
                    from_prop(pb, "rotation_euler", 0, f"thumb_curl.{side}", f"c*{curl:.3f}")
                    from_prop(pb, "rotation_euler", 2, f"finger_spread.{side}",
                              f"c*{0.18 if i == 1 else 0.04:.3f}")
                else:
                    from_prop(pb, "rotation_euler", 0, f"finger_curl.{side}", f"c*{curl:.3f}")
                    if i == 1:
                        spread = SPREAD_FACTORS.get(fname, 0.0)
                        from_prop(pb, "rotation_euler", 2, f"finger_spread.{side}",
                                  f"c*{spread * 0.42:.3f}")


def _setup_locks(arm, specs: list[BoneSpec]) -> None:
    for spec in specs:
        pb = arm.pose.bones.get(spec.name)
        if pb is None:
            continue
        if spec.deform:
            pb.lock_location = (True, True, True)
        pb.lock_scale = (True, True, True)


def _setup_display(arm) -> None:
    data = arm.data
    data.display_type = "OCTAHEDRAL"
    data.show_names = False
    data.show_axes = False
    data.pose_position = "POSE"
    arm.show_in_front = True


def _store_name_map(arm, specs: list[BoneSpec]) -> None:
    mapping = {spec.name: spec.name for spec in specs}
    arm[NAME_MAP_KEY] = json.dumps(mapping)


def _mark_asset(arm) -> None:
    try:
        if not arm.asset_data:
            arm.asset_mark()
            arm.asset_data.description = "Apex Rig & Motion human control rig"
        try:
            arm.asset_data.tags.new("Apex Rig")
            arm.asset_data.tags.new("Humanoid")
        except Exception:
            pass
    except Exception as exc:
        utils.log.debug("asset mark skipped: %s", exc)


def delete_rig(arm, remove_meshes_bindings: bool = True) -> None:
    if arm is None:
        return
    if remove_meshes_bindings:
        for ob in utils.meshes_of_armature(arm):
            for mod in list(ob.modifiers):
                if mod.type == "ARMATURE" and mod.object is arm:
                    ob.modifiers.remove(mod)
            if ob.parent is arm:
                world = ob.matrix_world.copy()
                ob.parent = None
                ob.matrix_world = world
    utils.safe_remove(arm)
    widgets.clear_widgets(remove_objects=True)


def build_rig(context, opts: RigOptions, name: str = RIG_NAME,
              replace: bool = True) -> BuildResult:
    utils.ensure_object_mode()
    existing = [ob for ob in bpy.data.objects if utils.is_apex_rig(ob)]
    if existing and replace:
        bpy.ops.object.select_all(action="DESELECT")
        for ob in existing:
            delete_rig(ob)

    proportions = HumanProportions(opts)
    specs = proportions.specs
    arm = _create_armature(context, name)
    arm.data.name = utils.unique_name(f"{name}-Data", bpy.data.armatures)

    _create_edit_bones(arm, specs)
    _setup_collections(arm, specs)
    _setup_colors(arm, specs)
    _setup_rotation_modes(arm, specs)
    _setup_widgets(arm, specs)
    _setup_display(arm)
    _setup_locks(arm, specs)

    arm[RIG_ID_KEY] = True
    arm[RIG_VERSION_KEY] = VERSION_STRING
    _store_name_map(arm, specs)
    _create_props(arm, opts)

    constraint_ctx: dict = {}
    for side in SIDE:
        _make_ik(arm, side, constraint_ctx, {s.name: s for s in specs}, opts)
        if opts.twist_bones:
            _make_twists(arm, side)
    _setup_ik_limits(arm)

    # solver calibration before the influence drivers exist
    if opts.pole_targets:
        for side in SIDE:
            ang_arm = _calibrate_pole(arm, side, "arm", Vector((0.0, -0.10 * proportions.H,
                                                               -0.12 * proportions.H)))
            ang_leg = _calibrate_pole(arm, side, "leg", Vector((0.0, 0.14 * proportions.H,
                                                               0.10 * proportions.H)))
            _set_prop(arm, f"pole_angle_arm.{side}", ang_arm)
            _set_prop(arm, f"pole_angle_leg.{side}", ang_leg)
            # make sure constraints sit at the calibrated angle before driving
            for con in list(arm.pose.bones[f"forearm.{side}"].constraints) + \
                    list(arm.pose.bones[f"shin.{side}"].constraints):
                if con.type == "IK" and con.pole_target:
                    con.pole_angle = ang_arm * DEG if "Arm" in con.name else ang_leg * DEG
    _setup_drivers(arm, opts)
    bpy.context.view_layer.update()
    try:
        Rig(arm).sync_selectability()
    except Exception as exc:
        utils.log.debug("selectability sync skipped: %s", exc)

    # keep the rig out of the way when another object is selected
    _mark_asset(arm)
    arm.select_set(True)
    context.view_layer.objects.active = arm
    return BuildResult(arm, proportions)


# ---------------------------------------------------------------------------
# Runtime wrapper
# ---------------------------------------------------------------------------
class Rig:
    """Stable, rename-safe access to an Apex rig."""

    def __init__(self, arm):
        self.obj = arm
        self.data = arm.data
        self._map = utils.from_json(arm.get(NAME_MAP_KEY, "{}"), {})
        self.props_bone_name = arm.get(PROPS_BONE + "_bone", PROPS_BONE)

    # -- names ------------------------------------------------------------
    def n(self, canonical: str) -> str:
        return self._map.get(canonical, canonical)

    def has(self, canonical: str) -> bool:
        return self.n(canonical) in self.data.bones

    def pb(self, canonical: str):
        return self.obj.pose.bones.get(self.n(canonical))

    def bone(self, canonical: str):
        return self.data.bones.get(self.n(canonical))

    def update_name_map(self, mapping: dict) -> None:
        self._map = mapping
        self.obj[NAME_MAP_KEY] = json.dumps(mapping)

    # -- properties -------------------------------------------------------
    @property
    def props_bone(self):
        return self.obj.pose.bones.get(self.props_bone_name) or (
            self.obj.pose.bones[0] if len(self.obj.pose.bones) else None)

    def get_prop(self, name: str, default=0.0) -> float:
        pb = self.props_bone
        if pb is None or name not in pb.keys():
            return float(default)
        return float(pb[name])

    def set_prop(self, name: str, value, refresh: bool = True) -> None:
        pb = self.props_bone
        if pb is not None and name in pb.keys():
            pb[name] = value
            if refresh:
                utils.refresh(self.obj)

    def prop_names(self) -> list[str]:
        pb = self.props_bone
        return [k for k in pb.keys() if k in PROPS] if pb else []

    def reset_properties(self) -> None:
        for name, spec in PROPS.items():
            self.set_prop(name, spec[0])

    # -- convenience ------------------------------------------------------
    def deform_bones(self) -> list[str]:
        return [b.name for b in self.data.bones if b.use_deform]

    def side_bones(self, template: str, side: str) -> str:
        return self.n(template.format(side=side))

    def get_vgroup_name(self, canonical: str) -> str:
        return self.n(canonical)

    def set_ik(self, limb: str, side: str, value: float, update: bool = True) -> None:
        self.set_prop(f"ik_{limb}.{side}", utils.clamp(value, 0.0, 1.0), refresh=update)
        try:
            self.sync_selectability()
        except Exception:
            pass

    def toggle_ik(self, limb: str, side: str) -> None:
        current = self.get_prop(f"ik_{limb}.{side}")
        self.set_ik(limb, side, 0.0 if current > 0.5 else 1.0)

    def sync_selectability(self) -> None:
        """Make it impossible to grab a deform bone that IK already controls.

        When a limb is on IK the hand/foot/toe/shin/forearm bones are driven by
        constraints, so rotating them by hand appears to "do nothing".  Hiding
        them from selection keeps animators on the controls.
        """
        for limb in ("arm", "leg"):
            chain = (("upper_arm", "forearm", "hand") if limb == "arm"
                     else ("thigh", "shin", "foot", "toe"))
            for side in ("L", "R"):
                try:
                    ik = self.get_prop(f"ik_{limb}.{side}")
                except Exception:
                    ik = 0.0
                hide = ik > 0.5
                for part in chain:
                    bone = self.bone(f"{part}.{side}")
                    if bone is not None:
                        bone.hide_select = hide

    def collection_visibility(self, name: str, visible: bool) -> None:
        coll = self.data.collections.get(name)
        if coll is not None:
            coll.is_visible = visible

    def collection_is_visible(self, name: str) -> bool:
        coll = self.data.collections.get(name)
        return bool(coll and coll.is_visible)

    # -- snapping ---------------------------------------------------------
    def snap_ik_to_fk(self, limb: str, side: str, sync_controls: bool = True) -> None:
        """Bake the current IK pose into the FK chain, then switch to FK."""
        if limb == "arm":
            chain = ["upper_arm", "forearm", "hand"]
            prop = f"ik_arm.{side}"
            controls = ["hand_ik"]
        else:
            chain = ["thigh", "shin", "foot", "toe"]
            prop = f"ik_leg.{side}"
            controls = ["foot_ik", "toe_ik"]

        matrices = {}
        for part in chain:
            pb = self.pb(f"{part}.{side}")
            if pb is not None:
                matrices[part] = pb.matrix.copy()
        ctl_mats = {}
        for part in controls:
            pb = self.pb(f"{part}.{side}")
            if pb is not None:
                ctl_mats[part] = pb.matrix.copy()
        eval_matrices = {}
        for part in chain:
            pb = self.pb(f"{part}.{side}")
            if pb is not None:
                eval_matrices[part] = pb.matrix.copy()

        self.set_prop(prop, 0.0)
        bpy.context.view_layer.update()
        for part in chain:
            pb = self.pb(f"{part}.{side}")
            if pb is not None and part in eval_matrices:
                pb.matrix = eval_matrices[part]
                bpy.context.view_layer.update()
        if sync_controls:
            for part in controls:
                pb = self.pb(f"{part}.{side}")
                if pb is not None and part in ctl_mats:
                    pb.matrix = ctl_mats[part]
                    bpy.context.view_layer.update()
        bpy.context.view_layer.update()

    def snap_fk_to_ik(self, limb: str, side: str, synced: bool = True) -> None:
        """Move the IK controls onto the current FK pose, then switch to IK."""
        if limb == "arm":
            pairs = [("hand_ik", "hand")]
            prop = f"ik_arm.{side}"
        else:
            pairs = [("foot_ik", "foot"), ("toe_ik", "toe")]
            prop = f"ik_leg.{side}"
        for ctl_part, src_part in pairs:
            ctl = self.pb(f"{ctl_part}.{side}")
            src = self.pb(f"{src_part}.{side}")
            if ctl is None or src is None:
                continue
            ctl.matrix = src.matrix.copy()
            bpy.context.view_layer.update()
        self.set_prop(prop, 1.0)
        bpy.context.view_layer.update()

    def mirror_pose(self) -> None:
        utils.mirror_pose(self.obj)
        side_props = ["ik_arm", "ik_leg", "finger_curl", "finger_spread",
                      "thumb_curl", "twist", "pole_angle_arm", "pole_angle_leg"]
        props_pb = self.props_bone
        for base in side_props:
            lname, rname = f"{base}.L", f"{base}.R"
            if props_pb is None or lname not in props_pb.keys() or rname not in props_pb.keys():
                continue
            a, b = props_pb[lname], props_pb[rname]
            props_pb[lname], props_pb[rname] = b, a
        bpy.context.view_layer.update()

    def bake_control_rig(self, name: str = "Apex_Controls_Baked"):
        """Snapshot every control channel into a new action (NLA stash)."""
        obj = self.obj
        action, slot = utils.new_action_for(obj, name)
        frame = bpy.context.scene.frame_current
        for pb in obj.pose.bones:
            paths = ["location", "scale"]
            if pb.rotation_mode == "QUATERNION":
                paths.append("rotation_quaternion")
            elif pb.rotation_mode == "AXIS_ANGLE":
                paths.append("rotation_axis_angle")
            else:
                paths.append("rotation_euler")
            for path in paths:
                try:
                    pb.keyframe_insert(path, frame=frame, group=pb.name)
                except Exception:
                    pass
            for key in pb.keys():
                if key in PROPS:
                    try:
                        pb.keyframe_insert(f'["{key}"]', frame=frame, group=pb.name)
                    except Exception:
                        pass
        return action, slot


def reset_properties(arm) -> None:
    rig = Rig(arm)
    rig.reset_properties()


def get_rig(obj=None) -> Rig | None:
    if obj is None:
        obj = utils.active_armature(require_apex=True)
    if obj is None:
        for candidate in bpy.data.objects:
            if utils.is_apex_rig(candidate):
                return Rig(candidate)
        return None
    if not utils.is_apex_rig(obj):
        return None
    return Rig(obj)
