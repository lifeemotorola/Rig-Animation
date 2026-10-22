import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
opts = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, opts, replace=True).arm
def head():
    bpy.context.view_layer.update()
    return tuple(round(v,3) for v in arm.pose.bones['head'].head)
print("built:", head(), flush=True)
# 1) remove all constraints
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='POSE')
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        pb.constraints.remove(c)
bpy.ops.object.mode_set(mode='OBJECT')
print("no constraints:", head(), flush=True)
# 2) flatten bbone segments
bpy.ops.object.mode_set(mode='EDIT')
for eb in arm.data.edit_bones:
    if eb.bbone_segments != 1:
        eb.bbone_segments = 1
bpy.ops.object.mode_set(mode='OBJECT')
print("segments=1:", head(), flush=True)
