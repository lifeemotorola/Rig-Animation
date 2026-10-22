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
    d={}
    for bn in ("pelvis","spine_01","head","hand.L","foot.L"):
        d[bn]=round((arm.pose.bones[bn].head-arm.data.bones[bn].head_local).length,4)
    pel=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ pel.matrix).to_euler()
    return d, tuple(round(v,4) for v in e)

print("no poles:", dev(build(pole_targets=False)), flush=True)

arm = build()
# unparent pole bones
bpy.ops.object.mode_set(mode='EDIT')
for side in ("L","R"):
    for n in (f"elbow_pole.{side}", f"knee_pole.{side}"):
        eb = arm.data.edit_bones[n]; eb.parent = None
bpy.ops.object.mode_set(mode='OBJECT')
print("poles unparented:", dev(arm), flush=True)

arm = build()
# remove all drivers
for fc in list(arm.animation_data.drivers): arm.animation_data.drivers.remove(fc)
print("no drivers:", dev(arm), flush=True)

arm = build()
# zero the ik_stretch driver by setting prop, and turn off stretch on constraints
for pb in arm.pose.bones:
    if pb.name.startswith(("forearm","shin")):
        for c in pb.constraints:
            if c.type=='IK': c.use_stretch=False
print("stretch off:", dev(arm), flush=True)
arm=build()
# what if leg IK chain_count=1? (shin only)
for side in ("L","R"):
    for c in arm.pose.bones[f"shin.{side}"].constraints:
        if c.type=='IK': c.chain_count=1
print("leg chain 1:", dev(arm), flush=True)
