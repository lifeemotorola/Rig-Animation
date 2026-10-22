import sys, math, time
sys.path.insert(0,'/home/user')
import bpy
from mathutils import Vector, Euler
import surigandanim
from surigandanim import rig as rigmod, skin_body, fit, utils, properties
surigandanim.register()
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- build a stand-in "user character": mannequin in a T-ish/A pose, odd transform
src = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("MALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, src, resolution=0.014)
# transform the character away from the origin and rotate it 120 degrees
body.parent = None
import mathutils
CHAR_XFORM = (mathutils.Matrix.Translation(Vector((3.2, -1.7, 0.55)))
              @ Euler((0, 0, math.radians(120))).to_matrix().to_4x4()
              @ mathutils.Matrix.Diagonal((0.85, 0.85, 0.85, 1.0)))
body.matrix_world = CHAR_XFORM
bpy.context.view_layer.update()
# ground-truth landmark positions from the original skeleton (world space)
GT = {}
for bn in ("pelvis","head","hand.L","hand.R","foot.L","foot.R","chest","thigh.L"):
    GT[bn] = CHAR_XFORM @ src.data.bones[bn].head_local
print("GT facing:", tuple(round(v,3) for v in (CHAR_XFORM.to_3x3() @ mathutils.Vector((0,-1,0))).normalized()), flush=True)
rigmod.delete_rig(src)             # character keeps its mesh + transform, no rig
utils.select_only([body]); bpy.context.view_layer.objects.active = body
dims = body.dimensions
print("character world dims:", tuple(round(v,3) for v in dims), "loc", tuple(round(v,2) for v in body.matrix_world.translation), flush=True)

# --- analyze
info = fit.analyze([body])
print("ANALYZE:", info.summary(), "| leg_len", round(info.leg_len,3), "center", tuple(round(v,2) for v in info.center), "floor", round(info.floor,3), flush=True)

# --- rig the character
st = properties.settings(bpy.context)
opts = properties.rig_options(st)
t0=time.time()
built, info, stats = fit.rig_character(bpy.context, [body], opts, refine=True)
arm = built.arm
print(f"RIG {round(time.time()-t0,2)}s bones={len(arm.data.bones)} height={opts.height:.3f} leg_len={opts.leg_len:.3f} arm_angle={opts.arm_angle:.1f}", flush=True)
print("rig placed at", tuple(round(v,3) for v in arm.location), "rot", round(math.degrees(arm.rotation_quaternion.to_euler().z),1), flush=True)
print("skin stats:", stats, flush=True)
rep = fit.joint_report(arm, [body])
print("JOINT FIT: inside", rep["inside"], "/", rep["bones"], "outside:", rep["outside"], "max surf dist", rep["max_distance"], flush=True)
print("--- landmark error vs original skeleton ---", flush=True)
errs=[]
for bn, gt in GT.items():
    new = arm.matrix_world @ arm.data.bones[bn].head_local
    e = (new-gt).length; errs.append(e)
    print(f"  {bn:8s} {e:.4f} m", flush=True)
print("MAX landmark error:", round(max(errs),4), flush=True)
