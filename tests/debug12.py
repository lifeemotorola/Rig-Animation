import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    o = RigOptions.from_preset("FEMALE")
    return rigmod.build_rig(bpy.context, o, replace=True).arm

def report(arm,tag):
    bpy.context.view_layer.update()
    sp = arm.pose.bones["spine_01"]
    pel = arm.pose.bones["pelvis"]
    print(f"{tag:26s} spine={tuple(round(v,3) for v in sp.head)} pelvis_head={tuple(round(v,3) for v in pel.head)} pel_mat_t={tuple(round(v,3) for v in pel.matrix.to_translation())} rest_t={tuple(round(v,3) for v in arm.data.bones['pelvis'].matrix_local.to_translation())}", flush=True)

arm=build(); report(arm,"all IK")
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='IK' and 'Arm' in c.name: pb.constraints.remove(c)
report(arm,"no ARM ik")
arm=build()
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='IK' and 'Leg' in c.name: pb.constraints.remove(c)
report(arm,"no LEG ik")
arm=build()
# only left leg ik disabled
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='IK' and c.subtarget=="foot_ik.L": pb.constraints.remove(c)
report(arm,"no LEG.L ik")
# inspect chain root: is thigh parented to pelvis; test pelvis locked?
arm=build()
for bn in ("pelvis","cog"):
    pb=arm.pose.bones[bn]
    print(bn, "lock_loc", pb.lock_location, "lock_rot", pb.lock_rotation, "inherit_scale", arm.data.bones[bn].inherit_scale, flush=True)
# what if pelvis parent changed to root instead of cog?
bpy.ops.object.mode_set(mode='EDIT')
eb=arm.data.edit_bones["pelvis"]; eb.parent=arm.data.edit_bones["root"]
bpy.ops.object.mode_set(mode='OBJECT')
report(arm,"pelvis->root parent")
