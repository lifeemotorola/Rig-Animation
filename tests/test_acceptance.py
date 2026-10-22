import sys, math, time
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector
import apex_rig
from apex_rig import rig as rigmod, utils, const
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
ok = lambda c: "PASS" if c else "FAIL"

# 1 rest pose
utils.refresh(arm)
rest_err = {n: round((arm.pose.bones[n].head - arm.data.bones[n].head_local).length, 4)
            for n in ("cog","pelvis","spine_02","chest","neck","head","hand.L","foot.L")}
print("1 rest pose:", rest_err, ok(max(rest_err.values()) < 0.006), flush=True)

# 2 IK + stretch on over-extension
f = arm.pose.bones["hand_ik.L"]; m = f.matrix.copy(); m.translation += Vector((0.10,0,0)); f.matrix = m
utils.refresh(arm)
over = (arm.pose.bones["hand.L"].head - f.head).length
R.set_prop("ik_stretch", 0.30)
over_s = (arm.pose.bones["hand.L"].head - f.head).length
print(f"2 over-reach err {over:.4f} -> with ik_stretch 0.3 {over_s:.4f}", ok(over_s < 0.02), flush=True)
R.set_prop("ik_stretch", 0.0)
f.matrix = m; f.matrix.translation -= Vector((0.10,0,0)); utils.refresh(arm)

# 3 fingers / pole props drive bones
def tip(n):
    utils.refresh(arm); return arm.pose.bones[n].tail.copy()
a=tip("f_middle_03.L"); R.set_prop("finger_curl.L",1.0); b=tip("f_middle_03.L")
print("3 finger curl moves %.4f m" % (b-a).length, ok((b-a).length>0.05), flush=True)
R.set_prop("finger_curl.L",0.0)
a=tip("f_pinky_03.L"); R.set_prop("finger_spread.L",1.0); b=tip("f_pinky_03.L")
print("3 finger spread moves %.4f m" % (b-a).length, ok((b-a).length>0.01), flush=True)
R.set_prop("finger_spread.L",0.0)
def knee():
    utils.refresh(arm); return arm.pose.bones["shin.L"].head.copy()
a=knee(); R.set_prop("pole_angle_leg.L",35.0); b=knee()
print("3 pole angle moves knee %.4f m" % (b-a).length, ok((b-a).length>0.02), flush=True)
R.set_prop("pole_angle_leg.L",-90.0)

# 4 IK/FK snapping
arm.pose.bones["upper_arm.L"].rotation_quaternion=(0.94,0.34,0,0)
utils.refresh(arm)
R.set_ik("arm","L",0.0); fk=arm.pose.bones["hand.L"].head.copy()
R.snap_fk_to_ik("arm","L"); err1=(arm.pose.bones["hand.L"].head-fk).length
R.snap_ik_to_fk("arm","L"); R.set_ik("arm","L",1.0); err2=(arm.pose.bones["hand.L"].head-fk).length
print(f"4 FK->IK {err1:.4f} IK->FK {err2:.4f}", ok(err1<0.001 and err2<0.001), flush=True)
bpy.ops.apex.reset_pose()

# 5 mirror
arm.pose.bones["upper_arm.L"].rotation_quaternion=(0.95,0.3,0.05,0)
utils.refresh(arm)
hl=arm.pose.bones["hand.L"].head.copy(); R.mirror_pose()
hr=arm.pose.bones["hand.R"].head.copy()
print("5 mirror L->R", tuple(round(v,3) for v in hl), tuple(round(v,3) for v in hr),
      ok(abs(hl.x+hr.x)<0.002 and abs(hl.y-hr.y)<0.002 and abs(hl.z-hr.z)<0.002), flush=True)
bpy.ops.apex.reset_pose()

# 6 walk quality
from apex_rig import animation as anim
walk = anim.create_motion(arm, "WALK")
arm.animation_data.action = walk
try: arm.animation_data.action_slot = walk.slots[0]
except Exception: pass
errs=[]; zs=[]
for fr in range(1,33):
    bpy.context.scene.frame_set(fr); bpy.context.view_layer.update()
    fl=arm.pose.bones["foot_ik.L"].head.copy()
    errs.append((arm.pose.bones["foot.L"].head-fl).length); zs.append(fl.z)
print(f"6 walk: max IK err {max(errs):.4f} m, foot lift {max(zs)-min(zs):.3f} m", ok(max(errs)<0.002), flush=True)

# 7 hips never move while posing limbs
bpy.ops.apex.clear_animation()
utils.refresh(arm)
p0 = arm.pose.bones["pelvis"].head.copy()
R.set_ik("leg","L",0.0)
arm.pose.bones["foot_ik.L"].matrix = arm.pose.bones["foot_ik.L"].matrix.copy()
fm = arm.pose.bones["foot_ik.L"].matrix.copy(); fm.translation += Vector((0,0.12,0.10))
arm.pose.bones["foot_ik.L"].matrix = fm
utils.refresh(arm)
p1 = arm.pose.bones["pelvis"].head.copy()
print("7 pelvis stable during leg IK:", round((p1-p0).length,5), ok((p1-p0).length<0.001), flush=True)

# 8 handles/manifests
import os
man = open('/home/user/apex_rig/blender_manifest.toml').read()
print("8 manifest", ok('blender_version_min = "5.2.0"' in man and 'id = "apex_rig"' in man), flush=True)
src = open('/home/user/apex_rig/__init__.py').read()
print("8 no bl_info assignment", ok('bl_info =' not in src and '__package__' not in src), flush=True)
