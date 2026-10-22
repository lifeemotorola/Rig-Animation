import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
from mathutils import Vector

def probe(stiff):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
    for pb in arm.pose.bones:
        if pb.name.startswith(("thigh","shin","upper_arm","forearm")):
            pb.ik_stiffness_y = stiff; pb.ik_stiffness_z = stiff
    bpy.context.view_layer.update()
    ikc=[c for c in arm.pose.bones["shin.L"].constraints if c.type=='IK'][0]
    ctl=arm.pose.bones["foot_ik.L"]; m=ctl.matrix.copy(); m.translation += Vector((0,0.05,0.12)); ctl.matrix=m
    bpy.context.view_layer.update(); k0=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
    ikc.pole_angle += 0.8; bpy.context.view_layer.update(); k1=tuple(round(v,3) for v in arm.pose.bones["shin.L"].head)
    ikc.pole_angle -= 0.8
    bpy.context.view_layer.update()
    err=(arm.pose.bones["foot.L"].head-ctl.head).length
    # pole alignment at this pose
    j=arm.pose.bones["thigh.L"].tail; root=arm.pose.bones["thigh.L"].head; tip=arm.pose.bones["shin.L"].tail
    axis=tip-root; clos=root+axis*((j-root).dot(axis)/axis.length_squared)
    p=arm.pose.bones["knee_pole.L"].head
    align=(j-clos).normalized().dot((p-clos).normalized())
    print(f"stiff={stiff}: reach_err={round(err,4)} pole_moves_knee={k0!=k1} align={round(align,3)}", flush=True)

for s in (0.0, 0.3, 0.75):
    probe(s)
