import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions

def pel(arm):
    bpy.context.view_layer.update()
    return round((arm.data.bones["pelvis"].matrix_local.inverted() @ arm.pose.bones["pelvis"].matrix).to_euler().x,4)

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
keep = {"root","cog","pelvis","spine_01","thigh.L","shin.L","foot.L","foot_ik.L","toe_ik.L","toe.L","knee_pole.L"}
bpy.ops.object.mode_set(mode='EDIT')
for eb in list(arm.data.edit_bones):
    if eb.name not in keep: arm.data.edit_bones.remove(eb)
bpy.ops.object.mode_set(mode='OBJECT')
print("trimmed:", pel(arm), flush=True)
# recreate IK from scratch on shin.L
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='IK': pb.constraints.remove(c)
print("no IK:", pel(arm), flush=True)
c = arm.pose.bones["shin.L"].constraints.new('IK'); c.target=arm; c.subtarget="foot_ik.L"; c.chain_count=2
print("fresh IK chain2:", pel(arm), "shin_tail", tuple(round(v,3) for v in arm.pose.bones['shin.L'].tail), flush=True)
c.chain_count=3
print("chain3:", pel(arm), flush=True)
c.chain_count=2
# strip all IK-related bone props to defaults
for bn in ("thigh.L","shin.L"):
    pb=arm.pose.bones[bn]
    pb.use_ik_limit_x=pb.use_ik_limit_y=pb.use_ik_limit_z=False
    pb.lock_ik_x=pb.lock_ik_y=pb.lock_ik_z=False
    pb.ik_stretch=1.0
    pb.use_ik_linear_control=False; pb.use_ik_rotation_control=False
print("fresh IK, default bone props:", pel(arm), "shin_tail", tuple(round(v,3) for v in arm.pose.bones['shin.L'].tail), flush=True)
print("chain members:", [p.name for p in arm.pose.bones if p.is_in_ik_chain], flush=True)
print("thigh local:", tuple(round(v,3) for v in arm.pose.bones['thigh.L'].rotation_quaternion), "shin local:", tuple(round(v,3) for v in arm.pose.bones['shin.L'].rotation_quaternion), flush=True)
