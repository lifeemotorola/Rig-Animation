import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

def test(tag, tweak):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
    tweak(arm)
    bpy.context.view_layer.update()
    out=[]
    for ctl_name, end in (("foot_ik.L","foot.L"),("hand_ik.L","hand.L")):
        ctl=arm.pose.bones[ctl_name]; m=ctl.matrix.copy(); m.translation += Vector((0,0,0.14)); ctl.matrix=m
        bpy.context.view_layer.update()
        out.append(round((arm.pose.bones[end].head-ctl.head).length,4))
        ctl.matrix=m  # reset approximately (matrix already moved; set back)
        mm=m.copy(); mm.translation -= Vector((0,0,0.14)); ctl.matrix=mm
        bpy.context.view_layer.update()
    print(f"{tag:34s} foot_err={out[0]} hand_err={out[1]}", flush=True)

test("baseline", lambda a: None)
def no_yz(a):
    for pb in a.pose.bones:
        pb.use_ik_limit_y=False; pb.use_ik_limit_z=False
test("no y/z limits", no_yz)
def no_limits(a):
    for pb in a.pose.bones:
        pb.use_ik_limit_x=pb.use_ik_limit_y=pb.use_ik_limit_z=False
test("no limits at all", no_limits)
def no_pole(a):
    for pb in a.pose.bones:
        for c in pb.constraints:
            if c.type=='IK': c.pole_target=None
test("no pole", no_pole)
def no_limits_no_pole(a):
    no_limits(a); no_pole(a)
test("no limits + no pole", no_limits_no_pole)
def stiff(a):
    for pb in a.pose.bones:
        pb.use_ik_limit_y=False; pb.use_ik_limit_z=False
        if pb.name.startswith(("thigh","shin","upper_arm","forearm")):
            pb.ik_stiffness_y=0.5; pb.ik_stiffness_z=0.5
test("no y/z + stiffness", stiff)
