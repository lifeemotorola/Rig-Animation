import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod, animation as anim, mocap, utils
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
tgt = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), name="Tgt", replace=True).arm
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), name="Src", replace=False).arm
act = anim.create_motion(src, "RUN")
print("candidates root:", mocap.canonical_candidates("root")[:6], flush=True)
print("candidates pelvis:", mocap.canonical_candidates("pelvis")[:6], flush=True)
R = rigmod.Rig(tgt)
bmap = mocap.build_bone_map(src, R, "MIXAMO")
print("map pelvis:", bmap.get("pelvis"), "cog:", bmap.get("cog"), "count", len(bmap), flush=True)
# sample source pelvis directly through same code path
for f in (1, 7):
    scene.frame_set(f); bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    se = src.evaluated_get(dg)
    print(f, "src pelvis matrix T", tuple(round(v,3) for v in se.pose.bones["pelvis"].matrix.translation), flush=True)
act2, rep = mocap.retarget(src, R, style="MIXAMO")
print("retarget:", rep["mapped"], rep["frames"], "hips:", rep["messages"], flush=True)
tgt.animation_data.action = act2
scene.frame_set(1); bpy.context.view_layer.update(); p1=tgt.pose.bones["pelvis"].head.copy()
scene.frame_set(7); bpy.context.view_layer.update(); p2=tgt.pose.bones["pelvis"].head.copy()
print("tgt pelvis", tuple(round(v,3) for v in p1), tuple(round(v,3) for v in p2), flush=True)
for fc in utils.action_fcurves(act2):
    if fc.data_path == 'pose.bones["pelvis"].location':
        print("pelvis loc", fc.array_index, [round(k.co.y,3) for k in fc.keyframe_points][:8], flush=True)
for fc in utils.action_fcurves(act2):
    if fc.data_path == 'pose.bones["cog"].location':
        print("cog loc", fc.array_index, [round(k.co.y,3) for k in fc.keyframe_points][:8], flush=True)
