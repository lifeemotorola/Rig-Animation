import sys
sys.path.insert(0,'/home/user')
import bpy, math
from surigandanim import rig as rigmod, animation as anim, utils
from surigandanim.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)

def head(n):
    utils.refresh(arm)
    return arm.pose.bones[n].head.copy()

for key in ("BREATHE","WALK"):
    act = anim.create_motion(arm, key)
    print(key, "action", act.name, "range", tuple(round(v,1) for v in utils.action_range(act)), "curves", len(utils.action_fcurves(act)), flush=True)

# evaluate walk
walk = anim.get_motion_action(arm, "WALK")
arm.animation_data.action = walk
try: arm.animation_data.action_slot = walk.slots[0]
except Exception: pass
prev=None; liftmax=0; planted=0
for f in range(1, 34):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    fl = arm.pose.bones["foot_ik.L"].head.copy()
    tgt = arm.pose.bones["shin.L"].tail
    if prev is not None:
        liftmax = max(liftmax, abs(fl.z - prev.z))
    prev = fl
print("walk foot_ik.L range over cycle: z min/max", flush=True)
zs=[]; ys=[]; errs=[]
for f in range(1,33):
    scene.frame_set(f); bpy.context.view_layer.update()
    fl=arm.pose.bones["foot_ik.L"].head.copy(); zs.append(fl.z); ys.append(fl.y)
    errs.append((arm.pose.bones["shin.L"].tail - fl).length)
print("z", round(min(zs),3), round(max(zs),3), "y", round(min(ys),3), round(max(ys),3), "ik err max", round(max(errs),4), flush=True)
per=[(f,round(e,4)) for f,e in zip(range(1,33),errs)]
print("worst frames:", sorted(per,key=lambda t:-t[1])[:5], flush=True)
# breathing
act = anim.get_motion_action(arm, "BREATHE"); arm.animation_data.action = act
try: arm.animation_data.action_slot = act.slots[0]
except Exception: pass
scene.frame_set(1); bpy.context.view_layer.update(); c0=arm.pose.bones["chest"].head.copy()
scene.frame_set(25); bpy.context.view_layer.update(); c1=arm.pose.bones["chest"].head.copy()
print("breath chest delta:", round((c1-c0).length,4), flush=True)
# fcurves cyclic?
fc = utils.action_fcurves(walk)[0]
print("cycle mods:", [m.type for m in fc.modifiers], "keys:", len(fc.keyframe_points), flush=True)
print("actions:", [a.name for a in bpy.data.actions], flush=True)
