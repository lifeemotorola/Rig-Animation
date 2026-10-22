import sys
sys.path.insert(0,'/home/user')
import bpy
from apex_rig import rig as rigmod
from apex_rig.proportions import RigOptions

def pel(arm):
    bpy.context.view_layer.update()
    p=arm.pose.bones["pelvis"]
    e=(arm.data.bones["pelvis"].matrix_local.inverted() @ p.matrix).to_euler()
    return round(e.x,4)

def run(tag, patch={}):
    import importlib
    importlib.reload(rigmod)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    saved={}
    for name,fn in patch.items():
        saved[name]=getattr(rigmod,name)
        setattr(rigmod,name,fn)
    try:
        arm=rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
        print(f"{tag:30s} pelvis_x={pel(arm)}", flush=True)
    finally:
        for name,fn in saved.items(): setattr(rigmod,name,fn)

run("full")
run("no widgets", {"_setup_widgets": lambda *a, **k: None})
run("no locks", {"_setup_locks": lambda *a, **k: None})
run("no drivers", {"_setup_drivers": lambda *a, **k: None})
run("no calibration", {"_calibrate_pole": lambda *a, **k: 0.0})
run("no colors", {"_setup_colors": lambda *a, **k: None})
run("no collections", {"_setup_collections": lambda *a, **k: None})
run("no ik limits", {"_setup_ik_limits": lambda *a, **k: None})
