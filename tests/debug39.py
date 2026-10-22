import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
bpy.context.view_layer.update()
# finger curl
tip0 = arm.pose.bones["f_middle_03.L"].tail.copy()
R.set_prop("finger_curl.L", 1.0); bpy.context.view_layer.update()
tip1 = arm.pose.bones["f_middle_03.L"].tail.copy()
print("curl moved finger:", round((tip1-tip0).length,3), "euler.x", round(arm.pose.bones["f_middle_01.L"].rotation_euler.x,3), flush=True)
R.set_prop("finger_curl.L", 0.0); bpy.context.view_layer.update()
# spread
t0 = arm.pose.bones["f_pinky_03.L"].tail.copy()
R.set_prop("finger_spread.L", 1.0); bpy.context.view_layer.update()
t1 = arm.pose.bones["f_pinky_03.L"].tail.copy()
print("spread moved pinky:", tuple(round(v,3) for v in (t1-t0)), flush=True)
R.set_prop("finger_spread.L", 0.0); bpy.context.view_layer.update()
# pole prop sensitivity
k0 = arm.pose.bones["shin.L"].head.copy()
R.set_prop("pole_angle_leg.L", 45.0); bpy.context.view_layer.update()
k1 = arm.pose.bones["shin.L"].head.copy()
print("pole prop moves knee:", round((k1-k0).length,4), flush=True)
R.set_prop("pole_angle_leg.L", -90.0); bpy.context.view_layer.update()
# IK/FK snap: pose FK arm then snap to IK
ua=arm.pose.bones["upper_arm.L"]; ua.rotation_quaternion = (0.966,0.259,0,0); ua.rotation_mode='QUATERNION'
fa=arm.pose.bones["forearm.L"]; fa.rotation_quaternion = (0.98,0,0.199,0)
bpy.context.view_layer.update()
hand_before = arm.pose.bones["hand.L"].head.copy() if False else None
R.set_prop("ik_arm.L", 0.0); bpy.context.view_layer.update()
fk_hand = arm.pose.bones["hand.L"].head.copy()
R.snap_fk_to_ik("arm","L"); bpy.context.view_layer.update()
ik_hand = arm.pose.bones["hand.L"].head.copy()
print("FK->IK snap err (hand):", round((ik_hand-fk_hand).length,4), "ikprop", R.get_prop("ik_arm.L"), flush=True)
R.snap_ik_to_fk("arm","L"); bpy.context.view_layer.update()
back = arm.pose.bones["hand.L"].head.copy()
print("IK->FK snap err (hand):", round((back-fk_hand).length,4), "ikprop", R.get_prop("ik_arm.L"), flush=True)
# mirror
R.set_prop("ik_arm.L",1.0); R.set_prop("ik_arm.R",1.0)
ctl=arm.pose.bones["hand_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0.1,-0.05,0.08)); ctl.matrix=m
bpy.context.view_layer.update()
lh = arm.pose.bones["hand.L"].head.copy()
R.mirror_pose(); bpy.context.view_layer.update()
rh = arm.pose.bones["hand.R"].head.copy()
print("mirror: left", tuple(round(v,3) for v in lh), "-> right", tuple(round(v,3) for v in rh), "expected", tuple(round(-lh.x,3) for _ in [0]), flush=True)
print("dist to mirrored:", round((rh-Vector((-lh.x, lh.y, lh.z))).length,4), flush=True)
