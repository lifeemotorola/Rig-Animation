import sys, traceback
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions, HumanProportions
bpy.ops.wm.read_factory_settings(use_empty=True)
opts = RigOptions.from_preset("FEMALE")
prop = HumanProportions(opts)
arm = rigmod.build_rig(bpy.context, opts, replace=True).arm
bpy.context.view_layer.update()
print("--- rest vs pose ---", flush=True)
for bn in ("pelvis","spine_01","spine_02","chest","neck","head","cog","root","hand.L","foot.L","shin.L","thigh.L"):
    b = arm.data.bones[bn]; pb = arm.pose.bones[bn]
    q = tuple(round(v,3) for v in pb.rotation_quaternion)
    loc = tuple(round(v,3) for v in pb.location)
    print(f"{bn:10s} rest={tuple(round(v,3) for v in b.head_local)} pose={tuple(round(v,3) for v in pb.head)} q={q} loc={loc}", flush=True)
print("expected head:", tuple(round(v,3) for v in prop.land['head']))
print("--- inverse kinematics influence ---")
for side in ("L","R"):
    for lim, b in (("arm","forearm"),("leg","shin")):
        for c in arm.pose.bones[f"{b}.{side}"].constraints:
            if c.type=='IK':
                print(lim, side, c.name, "infl", round(c.influence,3), "pole_angle_deg", round(c.pole_angle*57.2958,1), "disp", tuple(round(v,3) for v in c.pole_target.matrix_world.translation) if c.pole_target else None, flush=True)
print("--- what rotates head? ---")
print("head drivers:", [d.data_path for d in (arm.animation_data.drivers if arm.animation_data else []) if 'head' in d.data_path], flush=True)
print("head constraints:", [c.type for c in arm.pose.bones['head'].constraints], flush=True)
print("neck q:", tuple(round(v,3) for v in arm.pose.bones['neck'].rotation_quaternion), flush=True)
print("chest q:", tuple(round(v,3) for v in arm.pose.bones['chest'].rotation_quaternion), flush=True)
print("bbone head:", arm.pose.bones['head'].bbone_x, arm.pose.bones['neck'].bbone_x)
