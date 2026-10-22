import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

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
orig=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
props = {p.identifier: getattr(orig,p.identifier) for p in orig.bl_rna.properties if p.identifier not in ("rna_type",)}
print("ORIG:", {k:v for k,v in props.items() if k in ("influence","chain_count","use_stretch","use_tail","pole_target","pole_subtarget","pole_angle","iterations","use_tail","use_stretch","target","subtarget")}, flush=True)
print("orig pelvis:", pel(arm), flush=True)
# now flip individual props on the original
for k,v in (("pole_target",None),("use_stretch",False),("use_tail",True),("use_stretch",True)):
    setattr(orig,k,v)
    print(f"orig set {k}={v} ->", pel(arm), "shin_tail", tuple(round(x,3) for x in arm.pose.bones['shin.L'].tail), flush=True)
# restore pole and try pole angle values
orig.use_tail=False; orig.use_stretch=True
print("target:", orig.target, "subtarget:", orig.subtarget, flush=True)
print("pole:", orig.pole_target, orig.pole_subtarget, orig.pole_angle, flush=True)
# list all constraints on shin
print("constraints:", [(c.name,c.type) for c in arm.pose.bones["shin.L"].constraints], flush=True)
# check drivers on influence
if arm.animation_data:
    print("drivers on shin:", [(d.data_path, d.driver.expression) for d in arm.animation_data.drivers if "shin.L" in d.data_path], flush=True)
