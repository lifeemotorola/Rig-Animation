import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    opts = RigOptions.from_preset("FEMALE")
    return rigmod.build_rig(bpy.context, opts, replace=True).arm

def H(arm):
    bpy.context.view_layer.update()
    return tuple(round(v,3) for v in arm.pose.bones['head'].head)

arm=build()
print("baseline:", H(arm), flush=True)
# A: segments -> 1, keep constraints
bpy.context.view_layer.objects.active=arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for eb in arm.data.edit_bones:
    eb.bbone_segments = 1
bpy.ops.object.mode_set(mode='OBJECT')
print("A segments=1 (constraints kept):", H(arm), flush=True)

arm=build()
# B: remove only IK constraints
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='IK': pb.constraints.remove(c)
print("B no IK:", H(arm), flush=True)

arm=build()
# C: remove only copy rotation
for pb in arm.pose.bones:
    for c in list(pb.constraints):
        if c.type=='COPY_ROTATION': pb.constraints.remove(c)
print("C no copyrot:", H(arm), flush=True)

arm=build()
# D: what are actual influences / driver values?
for side in ("L",):
    for bn in ("forearm","shin"):
        for c in arm.pose.bones[f"{bn}.{side}"].constraints:
            print("  con", bn, c.name, "type", c.type, "influence", round(c.influence,3), "mute", c.mute, flush=True)
print("  prop ik_arm.L", arm.pose.bones["root"]["ik_arm.L"], "ik_leg.L", arm.pose.bones["root"]["ik_leg.L"], flush=True)
print("D:", H(arm), flush=True)
# E: set forearm IK influence 0 directly (bypass driver) and update
con=[c for c in arm.pose.bones["forearm.L"].constraints if c.type=='IK'][0]
con.influence=0.0
print("E after forearm.L ik infl=0:", H(arm), flush=True)
# F: set all bone ik_stretch 0
for pb in arm.pose.bones:
    pb.ik_stretch = 0.0
print("F after ik_stretch=0:", H(arm), flush=True)
# G: print pelvis/spine matrices rotation
import mathutils
for bn in ("pelvis","spine_01","spine_02"):
    m=arm.pose.bones[bn].matrix.to_3x3()
    e=m.to_euler()
    print("  rot", bn, tuple(round(v,4) for v in e), flush=True)
