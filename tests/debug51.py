import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def refresh():
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.view_layer.update()
def state():
    refresh()
    return (round(arm.pose.bones["f_middle_01.L"].rotation_euler.x,3),
            tuple(round(v,3) for v in arm.pose.bones["f_middle_03.L"].tail),
            round(arm.pose.bones["f_middle_03.L"].tail.y,3))
print("curl 0:", state()[0], flush=True)
R.set_prop("finger_curl.L", 1.0)
print("curl 1:", state()[0], flush=True)
R.set_prop("finger_curl.L", 0.0)
k0=state()[1]; R.set_prop("pole_angle_leg.L", 45.0); k1=state()[1]
print("pole knee delta:", round(sum((a-b)**2 for a,b in zip(k1,k0))**0.5,4), flush=True)
R.set_prop("pole_angle_leg.L", -90.0)
print("con influence ik_arm:", end=" ")
R.set_prop("ik_arm.L", 0.0); refresh()
print(arm.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
