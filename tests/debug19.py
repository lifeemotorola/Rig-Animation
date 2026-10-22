import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from mathutils import Vector

def build(**kw):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    o = RigOptions.from_preset("FEMALE")
    for k,v in kw.items(): setattr(o,k,v)
    return rigmod.build_rig(bpy.context, o, replace=True).arm

def dev(arm):
    bpy.context.view_layer.update()
    out={}
    for bn in ("pelvis","spine_01","head","hand.L","foot.L"):
        out[bn]=round((arm.pose.bones[bn].head-arm.data.bones[bn].head_local).length,4)
    pel=arm.pose.bones["pelvis"]
    delta=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix)
    return out, tuple(round(v,4) for v in delta.to_euler())

arm=build()
print("default:", dev(arm), flush=True)
# remove y/z ik limits everywhere
for pb in arm.pose.bones:
    pb.use_ik_limit_y=False; pb.use_ik_limit_z=False
print("no y/z limits:", dev(arm), flush=True)
ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.10,0.16)); ctl.matrix=m
bpy.context.view_layer.update(); k0=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
ikc.pole_angle=1.5; bpy.context.view_layer.update(); k1=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
print("leg pole sensitivity:", k0, k1, k0!=k1, flush=True)

arm=build()
for pb in arm.pose.bones:
    pb.use_ik_limit_y=False; pb.use_ik_limit_z=False
    pb.lock_ik_x=pb.lock_ik_y=pb.lock_ik_z=False
print("no y/z limits + no lock:", dev(arm), flush=True)

arm=build()
print("bbone off:", dev(arm, ), flush=True) if False else None
arm=build(bbone=False)
print("bbone=False:", dev(arm), flush=True)
arm=build(bbone=False, ik_arms=False, ik_legs=False)
print("bbone=False ik off:", dev(arm), flush=True)
