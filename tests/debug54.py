import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod, animation as anim, utils
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), name="Src", replace=True).arm
act = anim.create_motion(src, "RUN")
print("src action:", act.name, "range", utils.action_range(act), flush=True)
arm = src
for f in (1, 7, 13, 19):
    scene.frame_set(f); bpy.context.view_layer.update()
    ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pel = ev.pose.bones["pelvis"]
    cog = ev.pose.bones["cog"]
    print(f, "pelvis head", tuple(round(v,3) for v in pel.head), "root loc", tuple(round(v,3) for v in cog.location), flush=True)
# check fcurve for cog location
for fc in utils.action_fcurves(act):
    if fc.data_path == 'pose.bones["cog"].location':
        print("cog loc fc", fc.array_index, [(round(k.co.x),round(k.co.y,3)) for k in fc.keyframe_points][:4], flush=True)
