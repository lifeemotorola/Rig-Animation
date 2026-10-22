import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
bpy.ops.wm.read_factory_settings(use_empty=True)
o = RigOptions.from_preset("FEMALE")
arm = rigmod.build_rig(bpy.context, o, replace=True).arm
bpy.context.view_layer.update()
def spine(): 
    bpy.context.view_layer.update()
    return tuple(round(v,3) for v in arm.pose.bones["spine_01"].head)
print("with drivers:", spine(), flush=True)
n=0
for fc in list(arm.animation_data.drivers):
    arm.animation_data.drivers.remove(fc); n+=1
print("removed", n, "drivers ->", spine(), flush=True)
# re-add nothing; now check IK still solving: move hand target and see hand move
pb=arm.pose.bones["hand_ik.L"]
m=pb.matrix.copy(); m.translation = m.translation + __import__('mathutils').Vector((0,0,0.2)); pb.matrix=m
print("after moving hand_ik up:", tuple(round(v,3) for v in arm.pose.bones["hand.L"].head), "expected ~", tuple(round(v,3) for v in arm.pose.bones["hand_ik.L"].head), flush=True)
