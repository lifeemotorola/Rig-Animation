import sys, traceback
sys.path.insert(0, '/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions
from surigandanim import utils

report=[]
def p(*a): report.append(" ".join(str(x) for x in a))

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    opts = RigOptions.from_preset("FEMALE")
    res = rigmod.build_rig(bpy.context, opts, replace=True)
    arm = res.arm
    p("BUILD OK bones:", len(arm.data.bones))
    p("collections:", [(c.name, len(c.bones), c.is_visible) for c in arm.data.collections])
    pb = arm.pose.bones["root"]
    p("props:", {k: round(float(pb[k]),3) for k in pb.keys() if k.startswith(('ik','pole','fing','thumb','twist'))})
    p("forearm constraints:", [(c.type, c.name, round(c.influence,2)) for c in arm.pose.bones["forearm.L"].constraints])
    p("hand constraints:", [(c.type, round(c.influence,2)) for c in arm.pose.bones["hand.L"].constraints])
    drv = arm.animation_data.drivers if arm.animation_data else []
    p("drivers:", len(drv))
    for d in list(drv)[:6]:
        p("  drv", d.data_path, d.driver.expression, [(v.name, v.targets[0].data_path) for v in d.driver.variables])
    p("widget:", arm.pose.bones["hand_ik.L"].custom_shape.name if arm.pose.bones["hand_ik.L"].custom_shape else None, "scale", tuple(round(v,3) for v in arm.pose.bones["hand_ik.L"].custom_shape_scale_xyz))
    for bn in ("upper_arm.L","forearm.L","upper_arm.R","thigh.L","shin.L","foot.L","f_index_01.L","f_index_01.R","spine_02","head"):
        b = arm.data.bones[bn]
        m = b.matrix_local.to_3x3()
        p("axes", bn, "X", tuple(round(v,2) for v in m.col[0]), "Y", tuple(round(v,2) for v in m.col[1]), "Z", tuple(round(v,2) for v in m.col[2]))
    for bn in ("hand.L","hand.R","foot.L","head","toe.L","elbow_pole.L","wrist" ):
        if bn in arm.pose.bones:
            p("pos", bn, tuple(round(v,3) for v in arm.pose.bones[bn].head))
    bpy.context.view_layer.update()
    p("depsgraph ok")
    p("pole angles:", {k: round(float(pb[k]),1) for k in pb.keys() if k.startswith('pole_angle')})
except Exception:
    p("FAILED\n"+traceback.format_exc())
print("\n".join(report), flush=True)
