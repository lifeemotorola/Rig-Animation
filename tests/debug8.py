import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
for side in ("L",):
    for bn in ("forearm","shin"):
        for c in arm.pose.bones[f"{bn}.{side}"].constraints:
            print(bn, c.name, "chain_count", c.chain_count, "use_tail", c.use_tail, "use_stretch", c.use_stretch, "infl", round(c.influence,2), flush=True)
print("spine head:", tuple(round(v,3) for v in arm.pose.bones["spine_01"].head), flush=True)
# count connected chain upward
pb = arm.pose.bones["forearm.L"]
chain=[]
b=pb
for i in range(10):
    chain.append(b.name); 
    if not b.bone.use_connect or b.parent is None: break
    b=b.parent
print("connected upward:", chain, flush=True)
# set chain_count=2 explicitly
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.chain_count=2
bpy.context.view_layer.update()
print("after explicit chain_count=2:", tuple(round(v,3) for v in arm.pose.bones["spine_01"].head), flush=True)
# try chain_count=1
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.chain_count=1
bpy.context.view_layer.update()
print("chain_count=1:", tuple(round(v,3) for v in arm.pose.bones["spine_01"].head), flush=True)
# disable ik_stretch flag on constraints
for bn in ("forearm.L","forearm.R","shin.L","shin.R"):
    for c in arm.pose.bones[bn].constraints:
        if c.type=='IK': c.chain_count=2; c.use_stretch=False
bpy.context.view_layer.update()
print("use_stretch=False:", tuple(round(v,3) for v in arm.pose.bones["spine_01"].head), flush=True)
