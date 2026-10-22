import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def test(bbone, name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    opts = RigOptions.from_preset("FEMALE"); opts.bbone=bbone; opts.ik_arms=False; opts.ik_legs=False
    arm = rigmod.build_rig(bpy.context, opts, replace=True).arm
    bpy.context.view_layer.update()
    h = arm.pose.bones["head"]
    print(name, "head pose:", tuple(round(v,3) for v in h.head), "rest:", tuple(round(v,3) for v in arm.data.bones["head"].head_local), flush=True)
    print("   spine_01 pose:", tuple(round(v,3) for v in arm.pose.bones["spine_01"].head), "rest:", tuple(round(v,3) for v in arm.data.bones["spine_01"].head_local), flush=True)

test(True, "BBONE ON ")
test(False,"BBONE OFF")

# minimal repro: bbone segments on a non-connected chain with parent control
bpy.ops.wm.read_factory_settings(use_empty=True)
ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
e1=ad.edit_bones.new("cog"); e1.head=(0,0.013,0.882); e1.tail=(0,0.013,1.0)
e2=ad.edit_bones.new("pelvis"); e2.head=(0,0.013,0.899); e2.tail=(0,0.010,1.008); e2.parent=e1
e3=ad.edit_bones.new("spine"); e3.head=(0,0.010,1.008); e3.tail=(0,0.0,1.114); e3.parent=e2; e3.use_connect=True
e2.bbone_segments=3; e3.bbone_segments=3
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
for bn in ("pelvis","spine"):
    print("minimal", bn, "pose", tuple(round(v,3) for v in arm.pose.bones[bn].head), "rest", tuple(round(v,3) for v in ad.bones[bn].head_local), flush=True)
# now with bbone handles explicitly
bpy.ops.object.mode_set(mode='EDIT')
for e in ad.edit_bones:
    e.bbone_handle_type_start='AUTO'; e.bbone_handle_type_end='AUTO'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
print("after handle types:", tuple(round(v,3) for v in arm.pose.bones["spine"].head), flush=True)
