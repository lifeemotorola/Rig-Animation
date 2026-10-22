import sys, time
sys.path.insert(0,'/home/user')
import bpy, numpy as np
import apex_rig
from apex_rig import rig as rigmod, skin_body, skin, deform, utils
apex_rig.register()
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, rigmod.RigOptions.from_preset("FEMALE"), replace=True).arm
body = skin_body.add_mannequin(bpy.context, arm, resolution=0.014)
print("skin:", skin.weight_report(body, arm), flush=True)
cov = deform.bone_coverage(body, arm)
print("bones with no verts:", cov["empty"], "| min/max verts per bone:",
      min(cov["per_bone"].values()), max(cov["per_bone"].values()), flush=True)

t0=time.time()
rep = deform.deform_check(arm, body)
print(f"deform check in {round(time.time()-t0,2)}s: bones {rep['bones']}, empty {len(rep['empty_bones'])}, "
      f"stalled {rep['stalled']}, max displacement {rep['max_displacement']} m", flush=True)
print("  empty:", rep["empty_bones"], flush=True)
print("  stalled:", rep["stalled_bones"][:10], flush=True)
print("  weakest movers:", rep["weakest"], flush=True)

print("preserve volume:", deform.set_preserve_volume(arm, True), flush=True)
print("modifiers:", [(m.name, m.type, getattr(m,'use_deform_preserve_volume',None)) for m in body.modifiers], flush=True)
cs = deform.add_corrective_smooth(body)
print("corrective:", cs.name, cs.factor, cs.iterations, [m.name for m in body.modifiers], flush=True)
print("smooth weights:", deform.smooth_weights(body, iterations=2, factor=0.4), flush=True)
print("symmetrize:", deform.symmetrize_weights(body, "L_TO_R"), flush=True)
print("clean:", deform.clean_weights(body, threshold=1e-4, max_influences=4), flush=True)
print("heatmap:", deform.weight_heatmap(body, arm), flush=True)
attrs = [a.name for a in body.data.color_attributes]
print("color attributes:", attrs, flush=True)
rep2 = deform.deform_check(arm, body)
print("after tools: stalled", rep2["stalled"], "empty", len(rep2["empty_bones"]), flush=True)
