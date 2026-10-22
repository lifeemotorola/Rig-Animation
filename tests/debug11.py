import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    o = RigOptions.from_preset("FEMALE")
    return rigmod.build_rig(bpy.context, o, replace=True).arm

def spine(arm,tag):
    bpy.context.view_layer.update()
    print(f"{tag:38s} spine={tuple(round(v,3) for v in arm.pose.bones['spine_01'].head)} handL={tuple(round(v,3) for v in arm.pose.bones['hand.L'].head)}", flush=True)

arm=build(); spine(arm,"baseline")
# remove ik limits
for pb in arm.pose.bones:
    for ax in ("x","y","z"):
        setattr(pb, f"use_ik_limit_{ax}", False)
spine(arm,"ik limits off")
# unlock deform locations
for pb in arm.pose.bones:
    pb.lock_location=(False,False,False)
spine(arm,"locks off")
# set ik_stretch bone prop 0 & use_stretch False
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    pb=arm.pose.bones[bn]; pb.ik_stretch=0.0
    for c in pb.constraints:
        if c.type=='IK': c.use_stretch=False
spine(arm,"stretch off")
# clear widgets
for pb in arm.pose.bones:
    pb.custom_shape=None
spine(arm,"widgets cleared")
# remove copy rotation
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='COPY_ROTATION': pb.constraints.remove(c)
spine(arm,"copyrot removed")
# remove pole
for pb in arm.pose.bones:
    for c in pb.constraints:
        if c.type=='IK': c.pole_target=None
spine(arm,"pole removed")
# ik influence to 1.0 explicitly, target same place
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.influence=1.0; print("   con", bn, "chain", c.chain_count, "target", c.subtarget, flush=True)
spine(arm,"explicit infl")
# chain_count 1
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.chain_count=1
spine(arm,"chain 1")
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.chain_count=0
spine(arm,"chain 0 (all)")
