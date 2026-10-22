import sys, time
sys.path.insert(0,'/home/user')
import bpy, numpy as np
from mathutils import Vector
import apex_rig
from apex_rig import (rig as rigmod, skin_body, skin, deform, poses, animation as anim,
                      fit, properties, utils, ui_icons)
apex_rig.register()
ok = lambda c: "PASS" if c else "FAIL"
bpy.ops.wm.read_factory_settings(use_empty=True)
st = properties.settings(bpy.context)

# ---------- 1. every deform bone owns geometry -----------------------------
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.016)
cov = deform.bone_coverage(body, arm)
print("1 bone coverage:", len(cov["per_bone"]) - len(cov["empty"]), "/", len(cov["per_bone"]),
      "bones", ok(len(cov["empty"]) == 0), flush=True)

# ---------- 2. stress deformation ------------------------------------------
rep = deform.deform_check(arm, body)
print("2 deform check: stalled", rep["stalled"], "empty", len(rep["empty_bones"]),
      "max move", rep["max_displacement"], ok(rep["stalled"] == 0), flush=True)

# ---------- 3. animation coverage ------------------------------------------
walk = anim.create_motion(arm, "WALK")
cov2 = deform.animation_coverage(arm, body, walk)
print("3 animation coverage:", cov2["moving"], "/", cov2["total"], "bones move over",
      cov2["frames"], "frames; static:", cov2["static_bones"][:6], ok(not cov2["static_bones"]), flush=True)

# ---------- 4. poses --------------------------------------------------------
results = {}
for key in poses.POSE_LIBRARY:
    poses.apply_pose(arm, key)
    utils.refresh(arm)
    results[key] = (round(arm.pose.bones["head"].head.z, 2),
                    round(arm.pose.bones["foot.L"].head.z, 3))
print("4 poses:", {k: v for k, v in list(results.items())[:5]}, "...",
      ok(all(v[1] > 0.0 for v in results.values())), flush=True)
poses.clear_pose(arm)

# ---------- 5. deformation tools -------------------------------------------
pv = deform.set_preserve_volume(arm, True)
cs = deform.add_corrective_smooth(body, factor=0.4, iterations=8)
sm = deform.smooth_weights(body, iterations=2, factor=0.4)
sy = deform.symmetrize_weights(body, "L_TO_R")
cl = deform.clean_weights(body)
hm = deform.weight_heatmap(body, arm)
cov3 = deform.bone_coverage(body, arm)
print("5 tools: preserve", pv, "corrective", cs.name, "heatmap colours", hm["colors"],
      "| bones still covered:", len(cov3["per_bone"]) - len(cov3["empty"]),
      ok(len(cov3["empty"]) == 0), flush=True)

# ---------- 6. rig on a foreign character with the new weighting -----------
bpy.ops.wm.read_factory_settings(use_empty=True)
st = properties.settings(bpy.context)
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), replace=True).arm
char = skin_body.add_mannequin(bpy.context, src, resolution=0.02)
import mathutils
from mathutils import Euler
X = (mathutils.Matrix.Translation(Vector((2.0,-1.0,0.4)))
     @ Euler((0,0,1.0)).to_matrix().to_4x4()
     @ mathutils.Matrix.Diagonal((0.9,0.9,0.9,1.0)))
char.parent = src; char.matrix_parent_inverse = src.matrix_world.inverted()
src.parent = None; src.matrix_world = X
utils.select_only([char]); bpy.context.view_layer.objects.active = char
built, info, stats = fit.rig_character(bpy.context, [char], properties.rig_options(st))
arm2 = built.arm
cov4 = deform.bone_coverage(char, arm2)
rep4 = deform.deform_check(arm2, char)
print("6 character fit:", info.summary(), "| skin", stats[0]["method"],
      "| empty bones", len(cov4["empty"]), "| stalled", rep4["stalled_bones"],
      ok(len(cov4["empty"]) == 0 and rep4["stalled"] <= 2), flush=True)

# ---------- 7. picture data ------------------------------------------------
kinds = ui_icons.available_kinds()
counts = {k: len([f for f in __import__("os").listdir(ui_icons.preview_dir()) if f.startswith(k + "_")]) for k in kinds}
print("7 previews:", counts, ok(all(counts.get(k, 0) >= 4 for k in ("preset","pose","motion","skin"))), flush=True)

# ---------- 8. UI registration --------------------------------------------
panels = [n for n in dir(bpy.types) if n.startswith("APEX_PT")]
ops = [o for o in dir(bpy.ops.apex) if not o.startswith("_")]
print("8 ui:", len(panels), "panels,", len(ops), "operators", ok(len(panels) >= 8), flush=True)
