import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def run(bbone, ik, poles, tag):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    o = RigOptions.from_preset("FEMALE"); o.bbone=bbone; o.ik_arms=ik; o.ik_legs=ik; o.pole_targets=poles
    arm = rigmod.build_rig(bpy.context, o, replace=True).arm
    bpy.context.view_layer.update()
    pb = arm.pose.bones["spine_01"]
    print(f"{tag:34s} pose.head={tuple(round(v,3) for v in pb.head)} mat.transl={tuple(round(v,3) for v in pb.matrix.to_translation())} rest={tuple(round(v,3) for v in arm.data.bones['spine_01'].head_local)}", flush=True)

run(True,  True,  True,  "bbone+IK+poles")
run(False, True,  True,  "no bbone + IK + poles")
run(True,  True,  False, "bbone + IK no poles")
run(False, False, True,  "no bbone + no IK + poles")
