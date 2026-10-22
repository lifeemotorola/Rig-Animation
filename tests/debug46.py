import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
ad = bpy.data.armatures.new("A"); arm = bpy.data.objects.new("A", ad)
bpy.context.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = ad.edit_bones.new("b"); eb.head=(0,0,0); eb.tail=(0,0,1)
bpy.ops.object.mode_set(mode='OBJECT')
pb = arm.pose.bones["b"]; pb.rotation_mode='XYZ'
arm["curl"] = 0.0
fc = pb.driver_add("rotation_euler", 0)
d = fc.driver; d.type='SCRIPTED'; d.expression='curl*1.5'
v = d.variables.new(); v.name='curl'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='["curl"]'
bpy.context.view_layer.update()
arm["curl"]=1.0
bpy.context.view_layer.update()
ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
print("props:" if False else "", end="")
print("simple", d.is_simple_expression, "valid", d.is_valid, flush=True)
print("orig euler:", tuple(round(x,3) for x in pb.rotation_euler), "eval euler:", tuple(round(x,3) for x in ev.pose.bones['b'].rotation_euler), flush=True)
bpy.context.scene.frame_set(2)
ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
print("after frame_set eval euler:", tuple(round(x,3) for x in ev.pose.bones['b'].rotation_euler), flush=True)
# variant: driver on a custom prop of armature (not pose bone)
print("drivers valid:", [(x.data_path, x.driver.is_valid) for x in arm.animation_data.drivers], flush=True)
# check if the bone has animation_data? pose bones don't
print("pool:", ad.edit_bones["b"].use_deform, flush=True)
