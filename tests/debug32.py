import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
bpy.context.view_layer.update()
bad=[(pb.name, round((pb.head-pb.bone.head_local).length,4)) for pb in arm.pose.bones if (pb.head-pb.bone.head_local).length>2e-3]
print("off-rest bones:", bad, flush=True)
for bn in ("hand.L","foot.L","head"):
    print(bn,"pose",tuple(round(v,3) for v in arm.pose.bones[bn].head),"rest",tuple(round(v,3) for v in arm.data.bones[bn].head_local), flush=True)
pb=arm.pose.bones["root"]
print("pole angles:", {k: round(float(pb[k]),1) for k in pb.keys() if k.startswith("pole_angle")}, flush=True)
# functional IK test: move foot control up 15cm, hand control up 10cm
f=arm.pose.bones["foot_ik.L"]; m=f.matrix.copy(); m.translation.z += 0.15; f.matrix=m
h=arm.pose.bones["hand_ik.L"]; m2=h.matrix.copy(); m2.translation.z += 0.10; h.matrix=m2
bpy.context.view_layer.update()
print("foot bone vs target:", tuple(round(v,3) for v in arm.pose.bones["foot.L"].head), tuple(round(v,3) for v in f.head), "dist", round((arm.pose.bones["foot.L"].head-f.head).length,4), flush=True)
print("hand bone vs target:", tuple(round(v,3) for v in arm.pose.bones["hand.L"].head), tuple(round(v,3) for v in h.head), "dist", round((arm.pose.bones["hand.L"].head-h.head).length,4), flush=True)
# elbows/knees direction check vs poles
for side in ("L","R"):
    for limb,upper,lower,pole in (("arm","upper_arm","forearm","elbow_pole"),("leg","thigh","shin","knee_pole")):
        j=arm.pose.bones[f"{upper}.{side}"].tail; root=arm.pose.bones[f"{upper}.{side}"].head; tip=arm.pose.bones[f"{lower}.{side}"].tail
        axis=tip-root; clos=root+axis*((j-root).dot(axis)/axis.length_squared)
        p=arm.pose.bones[f"{pole}.{side}"].head
        print(limb, side, "joint->pole dir dot:", round((j-clos).normalized().dot((p-clos).normalized()),3), flush=True)
