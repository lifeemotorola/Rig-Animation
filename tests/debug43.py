import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
def ev():
    bpy.context.view_layer.update()
    return arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
def head(name):
    return ev().pose.bones[name].head.copy()

tip0 = head("f_middle_03.L")
R.set_prop("finger_curl.L", 1.0)
tip1 = head("f_middle_03.L")
print("curl moved finger:", round((tip1-tip0).length,3), flush=True)
R.set_prop("finger_curl.L", 0.0)
s0 = head("f_pinky_03.L"); R.set_prop("finger_spread.L", 1.0); s1 = head("f_pinky_03.L")
print("spread pinky delta:", tuple(round(v,4) for v in (s1-s0)), flush=True)
R.set_prop("finger_spread.L", 0.0)
k0 = head("shin.L"); R.set_prop("pole_angle_leg.L", 45.0); k1 = head("shin.L")
print("pole moves knee:", round((k1-k0).length,4), flush=True)
R.set_prop("pole_angle_leg.L", -90.0)
# IK reach through evaluated
f=arm.pose.bones["foot_ik.L"]; m=f.matrix.copy(); m.translation += Vector((0,0,0.15)); f.matrix=m
fb=head("foot.L"); fh=head("foot_ik.L")
print("IK reach err:", round((fb-fh).length,4), flush=True)
f.matrix=m.copy(); f.matrix.translation = m.translation - Vector((0,0,0.15))
# FK->IK snap with evaluated reads
ua=arm.pose.bones["upper_arm.L"]; ua.rotation_quaternion=(0.966,0.259,0,0)
arm.pose.bones["forearm.L"].rotation_quaternion=(0.98,0,0.199,0)
R.set_prop("ik_arm.L", 0.0)
fk = head("hand.L")
R.snap_fk_to_ik("arm","L")
ik = head("hand.L")
print("FK->IK snap err:", round((ik-fk).length,4), flush=True)
R.snap_ik_to_fk("arm","L")
back = head("hand.L")
print("IK->FK snap err:", round((back-fk).length,4), flush=True)
