import sys
sys.path.insert(0,'/home/user')
import bpy, numpy as np
from mathutils import Vector
import apex_rig
from apex_rig import rig as rigmod, skin_body, skin, utils, properties, fit
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)

# character with DIFFERENT proportions than the rig (thicker fingers/hands, bigger head)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.012)
# scale up hands/head to emulate a stylized character
me = body.data
for v in me.vertices:
    if v.co.z > 1.52:
        v.co = Vector((v.co.x*1.25, v.co.y*1.25, 1.52 + (v.co.z-1.52)*1.25))
rep = skin.weight_report(body, arm)
print("report:", rep, flush=True)

# per-bone weighted vertex counts
gi = {g.index: g.name for g in body.vertex_groups}
counts = {}
for v in me.vertices:
    for ge in v.groups:
        if ge.weight > 0.01:
            counts[gi[ge.group]] = counts.get(gi[ge.group], 0) + 1
bones = [b.name for b in arm.data.bones if b.use_deform]
missing = [b for b in bones if counts.get(b,0) == 0]
print("deform bones:", len(bones), "bones with NO weighted vertices:", len(missing), missing[:20], flush=True)
for b in ("head","neck","hand.L","f_index_01.L","f_index_03.L","thumb_03.L","foot.L","toe.L","shin.L"):
    print(f"  {b:14s} verts {counts.get(b,0)}", flush=True)

# does the character mesh actually follow finger curl?
dg = bpy.context.evaluated_depsgraph_get()
def sample():
    ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.data
    n=len(m.vertices); co=np.empty(n*3); m.vertices.foreach_get("co", co)
    return co.reshape(n,3).copy()
R = rigmod.Rig(arm)
a = sample()
R.set_prop("finger_curl.L", 1.0)
b = sample()
d = np.linalg.norm(a-b, axis=1)
print("finger curl: verts moved >1mm:", int((d>0.001).sum()), "max", round(float(d.max()),4), flush=True)
R.set_prop("finger_curl.L", 0.0)
a = sample()
arm.pose.bones["head"].rotation_quaternion = (0.94, 0, 0.34, 0)
utils.refresh(arm)
b = sample(); d = np.linalg.norm(a-b, axis=1)
print("head turn: verts moved >1mm:", int((d>0.001).sum()), "max", round(float(d.max()),4), flush=True)
arm.pose.bones["head"].rotation_quaternion = (1,0,0,0); utils.refresh(arm)
a = sample()
arm.pose.bones["toe_ik.L"].rotation_quaternion = (0.98, 0.2, 0, 0)
utils.refresh(arm)
b = sample(); d = np.linalg.norm(a-b, axis=1)
print("toe_ik bend: verts moved >1mm:", int((d>0.001).sum()), "max", round(float(d.max()),4), flush=True)
