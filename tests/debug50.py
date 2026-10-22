import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def tip(name):
    bpy.context.view_layer.update(); bpy.context.view_layer.update()
    return arm.pose.bones[name].tail.copy()
t0 = tip("f_middle_03.L")
R.set_prop("finger_curl.L", 1.0)
t1 = tip("f_middle_03.L")
print("curl moves finger (orig):", round((t1-t0).length,4), "euler", round(arm.pose.bones["f_middle_01.L"].rotation_euler.x,3), flush=True)
R.set_prop("finger_curl.L", 0.0)
s0 = tip("f_pinky_03.L"); R.set_prop("finger_spread.L", 1.0); s1 = tip("f_pinky_03.L")
print("spread pinky delta:", tuple(round(v,4) for v in (s1-s0)), flush=True)
R.set_prop("finger_spread.L", 0.0)
k0 = tip("shin.L"); R.set_prop("pole_angle_leg.L", 45.0); k1 = tip("shin.L")
print("pole moves knee:", round((k1-k0).length,4), flush=True)
R.set_prop("pole_angle_leg.L", -90.0)
# thumb
th0 = tip("thumb_03.L"); R.set_prop("thumb_curl.L", 1.0); th1 = tip("thumb_03.L")
print("thumb curl moves:", round((th1-th0).length,4), flush=True)
