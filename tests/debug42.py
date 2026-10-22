import sys
sys.path.insert(0,'/home/user')
import bpy
from surigandanim import rig as rigmod
from surigandanim.proportions import RigOptions

bpy.ops.wm.read_factory_settings(use_empty=True)
arm = rigmod.build_rig(bpy.context, RigOptions.from_preset("FEMALE"), replace=True).arm
R = rigmod.Rig(arm)
d0 = list(arm.animation_data.drivers)[0]
print("path:", d0.data_path, "array_index:", d0.array_index, "mute:", d0.mute, "var names:", [v.name for v in d0.driver.variables], flush=True)
print("manual evaluate(1.0):", d0.evaluate(1.0), flush=True)
R.set_prop("ik_arm.L", 0.3)
bpy.context.view_layer.update()
d0.update()  # force driver re-eval? not a thing but try
print("evaluate after prop=0.3:", d0.evaluate(1.0), flush=True)
ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
print("evaluated con influence:", ev.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, "orig:", arm.pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
print("bone prop value:", arm.pose.bones["root"]["ik_arm.L"], "evaluated prop:", ev.pose.bones["root"]["ik_arm.L"], flush=True)
# try a hand-made driver on the same constraint
c = arm.pose.bones["forearm.L"].constraints["APEX IK Arm"]
fc = c.driver_add("influence")
dr = fc.driver; dr.type='SCRIPTED'; dr.expression='x'
v=dr.variables.new(); v.name='x'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='pose.bones["root"]["ik_arm.L"]'
print("manual driver vars:", [vv.name for vv in dr.variables], "valid:", dr.is_valid, "simple:", dr.is_simple_expression, flush=True)
print("manual evaluate:", fc.evaluate(1.0), flush=True)
bpy.context.view_layer.update()
print("influence now:", c.influence, flush=True)
print("evaluated influence:", arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones["forearm.L"].constraints["APEX IK Arm"].influence, flush=True)
