import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def euler(): return round(arm.pose.bones["f_middle_01.L"].rotation_euler.x,3)
R.set_prop("finger_curl.L", 1.0)
print("plain update:", (bpy.context.view_layer.update(), euler())[1], flush=True)
arm.update_tag()
bpy.context.view_layer.update()
print("update_tag():", euler(), flush=True)
arm.update_tag(refresh={'TIME','OBJECT'})
bpy.context.view_layer.update()
print("update_tag TIME+OBJECT:", euler(), flush=True)
bpy.context.view_layer.depsgraph.update()
print("depsgraph.update:", euler(), flush=True)
try:
    bpy.context.evaluated_depsgraph_get().update()
    print("evaluated_depsgraph.update:", euler(), flush=True)
except Exception as e: print("dg err", e, flush=True)
bpy.ops.wm.save_as_mainfile(filepath="/tmp/t.blend")
print("after save:", euler(), flush=True)
bpy.context.scene.frame_set(1)
print("frame_set 1:", euler(), flush=True)
