import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
print("IK chain members:", [pb.name for pb in arm.pose.bones if pb.is_in_ik_chain], flush=True)
for bn in ("pelvis","thigh.L","shin.L","foot.L","spine_01"):
    pb=arm.pose.bones[bn]
    print(bn, "in_ik", pb.is_in_ik_chain, "lock_rot", tuple(pb.lock_rotation), "ik_stiff", (pb.ik_stiffness_x,pb.ik_stiffness_y,pb.ik_stiffness_z), "use_limit_x", pb.use_ik_limit_x, flush=True)
# leg chain count effect on pelvis matrix
import mathutils
pel = arm.pose.bones["pelvis"]
rest = arm.data.bones["pelvis"].matrix_local
delta = rest.inverted() @ pel.matrix
print("pelvis local delta euler:", tuple(round(v,4) for v in delta.to_euler()), "loc", tuple(round(v,4) for v in delta.to_translation()), flush=True)
# try chain=3 vs 2 vs 1 while measuring spine
def spine(): 
    bpy.context.view_layer.update(); return tuple(round(v,3) for v in arm.pose.bones["spine_01"].head)
for cc in (1,2,3,0):
    for bn in ("shin.L","shin.R"):
        for c in arm.pose.bones[bn].constraints:
            if c.type=='IK': c.chain_count=cc
    print("leg chain",cc,"-> spine",spine(), flush=True)
