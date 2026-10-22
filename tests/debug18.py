import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
from mathutils import Vector

for prop in ("lock_ik_x","ik_stretch","use_ik_linear_control","ik_linear_weight","use_ik_limit_x"):
    p = bpy.types.PoseBone.bl_rna.properties.get(prop)
    print(prop, "=>", p.description if p else None, flush=True)

def build(**kw):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    o = RigOptions.from_preset("FEMALE")
    for k,v in kw.items(): setattr(o,k,v)
    return rigmod.build_rig(bpy.context, o, replace=True).arm

def spine(arm):
    bpy.context.view_layer.update()
    return round((arm.pose.bones["spine_01"].head - arm.data.bones["spine_01"].head_local).length,4)
def knee(arm):
    bpy.context.view_layer.update()
    return tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)

arm=build()
print("\n--- default (lock on) ---", flush=True)
print("spine dev", spine(arm), "knee", knee(arm), flush=True)
# pole sensitivity test: move foot target forward+up, compare two angles
ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.10,0.16)); ctl.matrix=m
bpy.context.view_layer.update()
k0=knee(arm)
ikc.pole_angle=1.5; bpy.context.view_layer.update(); k1=knee(arm)
print("pole 0 vs 1.5 knee:", k0, k1, "different:", k0!=k1, flush=True)

arm=build()
print("\n--- lock off, ik_stretch=0 everywhere ---", flush=True)
for p in arm.pose.bones:
    p.lock_ik_x=p.lock_ik_y=p.lock_ik_z=False
    p.ik_stretch=0.0
print("spine dev", spine(arm), "knee", knee(arm), flush=True)
ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.10,0.16)); ctl.matrix=m
bpy.context.view_layer.update(); k0=knee(arm)
ikc.pole_angle=1.5; bpy.context.view_layer.update(); k1=knee(arm)
print("pole 0 vs 1.5 knee:", k0, k1, "different:", k0!=k1, flush=True)

arm=build()
print("\n--- lock only X on chain roots ---", flush=True)
for bn in ("thigh.L","thigh.R","upper_arm.L","upper_arm.R"):
    p=arm.pose.bones[bn]; p.lock_ik_x=True; p.lock_ik_y=False; p.lock_ik_z=False
print("spine dev", spine(arm), flush=True)
ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.10,0.16)); ctl.matrix=m
bpy.context.view_layer.update(); k0=knee(arm)
ikc.pole_angle=1.5; bpy.context.view_layer.update(); k1=knee(arm)
print("pole 0 vs 1.5 knee:", k0, k1, "different:", k0!=k1, flush=True)
