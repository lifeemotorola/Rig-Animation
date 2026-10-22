import sys, os, math, time
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector, Matrix
import apex_rig
from apex_rig import rig as rigmod, animation as anim, mocap, export as apex_export, utils, skin

apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
st = scene.apex_settings
st.height = 1.68; st.add_mannequin = True; st.mannequin_resolution = 0.03
t0=time.time()
bpy.ops.apex.build_rig()
arm = utils.active_armature(require_apex=True)
R = rigmod.Rig(arm)
print("BUILD", len(arm.data.bones), "bones,", len([o for o in bpy.data.objects if o.type=='MESH' and o.parent==arm]), "mesh,", round(time.time()-t0,2), "s", flush=True)

# ---- pose ops
bpy.ops.apex.toggle_ik(limb="arm", side="L")
print("toggle ik_arm.L ->", R.get_prop("ik_arm.L"), flush=True)
bpy.ops.apex.toggle_ik(limb="arm", side="L")
print("toggle back ->", R.get_prop("ik_arm.L"), flush=True)
arm.pose.bones["upper_arm.L"].rotation_quaternion = (0.96, 0.28, 0, 0)
bpy.ops.apex.mirror_pose()
q = arm.pose.bones["upper_arm.R"].rotation_quaternion
print("mirror q R:", tuple(round(v,3) for v in q), flush=True)
bpy.ops.apex.reset_pose()
print("reset pose:", tuple(round(v,3) for v in arm.pose.bones["upper_arm.L"].rotation_quaternion), flush=True)

# ---- motion + bake + mirror
st.motion="WALK"; st.motion_push_nla=False
bpy.ops.apex.add_motion()
walk = anim.get_motion_action(arm, "WALK")
print("walk curves:", len(utils.action_fcurves(walk)), "range", utils.action_range(walk), flush=True)
t0=time.time()
baked = anim.bake_action(arm, walk, "Walk_Baked", 1, 33)
print("baked curves:", len(utils.action_fcurves(baked)), "in", round(time.time()-t0,2),"s", flush=True)
mir = anim.mirror_action(arm, walk, "Walk_Mirror")
print("mirror curves:", len(utils.action_fcurves(mir)), flush=True)

def foot(side, action, frame):
    arm.animation_data.action = action
    try: arm.animation_data.action_slot = action.slots[0]
    except Exception: pass
    scene.frame_set(frame); bpy.context.view_layer.update()
    return arm.pose.bones[f"foot_ik.{side}"].head.copy()
a = foot("L", walk, 9); b = foot("R", mir, 9)
print("mirror check L(orig) vs R(mirror):", tuple(round(v,3) for v in a), tuple(round(v,3) for v in b), flush=True)

# ---- retarget from a second apex rig (source has apex names)
src_res = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), name="MocapSource", replace=False)
src = src_res.arm
anim.create_motion(src, "RUN")
print("source action:", src.animation_data.action.name if src.animation_data and src.animation_data.action else None, flush=True)
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = arm
for ob in bpy.data.objects: ob.select_set(ob in (arm, src))
t0=time.time()
act, rep = mocap.retarget(src, R, style="MIXAMO", match_scale=True)
print("retarget:", rep["frames"], "frames,", rep["mapped"], "bones, scale", rep["scale"], "in", round(time.time()-t0,2),"s", flush=True)
print("retarget curves:", len(utils.action_fcurves(act)), flush=True)
arm.animation_data.action = act
try: arm.animation_data.action_slot = act.slots[0]
except Exception: pass
scene.frame_set(1); bpy.context.view_layer.update(); p1=arm.pose.bones["pelvis"].head.copy()
scene.frame_set(7); bpy.context.view_layer.update(); p2=arm.pose.bones["pelvis"].head.copy()
print("retarget pelvis moved:", round((p2-p1).length,4), flush=True)

# ---- name map from mixamo-named source
srcR = rigmod.Rig(src)
n = mocap.rename_to_style(srcR, "MIXAMO")
print("renamed source bones to mixamo:", n, "sample:", [b.name for b in src.data.bones if "LeftArm" in b.name][:2], flush=True)
bmap = mocap.build_bone_map(src, R, "MIXAMO")
print("mixamo bone map size:", len(bmap), "sample:", list(bmap.items())[:4], flush=True)

# ---- game naming on target
n = mocap.rename_to_style(R, "UE5")
print("UE5 renamed:", n, "upper_arm.L ->", R.n("upper_arm.L"), "map lookup ok:", "upperarm_l" in arm.data.bones, flush=True)

# ---- export
os.makedirs("/home/user/out", exist_ok=True)
st.export_path = "/home/user/out/apex_character.glb"
st.export_selection = True
t0=time.time()
res = bpy.ops.apex.export()
glb = "/home/user/out/apex_character.glb"
print("glb export:", res, os.path.getsize(glb), "bytes in", round(time.time()-t0,2),"s", flush=True)
st.export_preset = "FBX_UNITY"; st.export_path = "/home/user/out/apex_character.fbx"
t0=time.time()
res = bpy.ops.apex.export()
fbx = "/home/user/out/apex_character.fbx"
print("fbx export:", res, os.path.getsize(fbx), "bytes in", round(time.time()-t0,2),"s", flush=True)
bpy.ops.wm.save_as_mainfile(filepath="/home/user/out/apex_demo.blend")
print("saved blend:", os.path.getsize("/home/user/out/apex_demo.blend"), flush=True)
