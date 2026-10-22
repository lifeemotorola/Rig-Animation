import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
def diff(pb):
    rest = pb.bone.matrix_local
    return (pb.matrix.inverted() @ rest).to_euler(), (pb.matrix.to_translation()-rest.to_translation())
for bn in ("root","cog","pelvis","spine_01","spine_02","chest"):
    pb=arm.pose.bones[bn]
    e,t = diff(pb)
    print(f"{bn:9s} basis_loc={tuple(round(v,4) for v in pb.matrix_basis.to_translation())} basis_eul={tuple(round(v,4) for v in pb.matrix_basis.to_euler())} delta_loc={tuple(round(v,4) for v in t)} delta_eul={tuple(round(v,4) for v in e)}", flush=True)
# mute all constraints and see
for pb in arm.pose.bones:
    for c in pb.constraints: c.mute=True
bpy.context.view_layer.update()
print("all muted: spine", tuple(round(v,3) for v in arm.pose.bones['spine_01'].head), "handL", tuple(round(v,3) for v in arm.pose.bones['hand.L'].head), flush=True)
for pb in arm.pose.bones:
    for c in pb.constraints: c.mute=False
# mute only IK
for pb in arm.pose.bones:
    for c in pb.constraints:
        if c.type=='IK': c.mute=True
bpy.context.view_layer.update()
print("IK muted: spine", tuple(round(v,3) for v in arm.pose.bones['spine_01'].head), flush=True)
