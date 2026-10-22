import bpy, math, sys
from mathutils import Vector
out=[]
def p(*a): out.append(" ".join(str(x) for x in a))

sc=bpy.context.scene
# 1 armature/edit bones/bone collections
arm_data=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",arm_data)
sc.collection.objects.link(arm); bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
eb=arm_data.edit_bones.new("root"); eb.head=(0,0,0); eb.tail=(0,0,1)
eb2=arm_data.edit_bones.new("child"); eb2.head=(0,0,1); eb2.tail=(0,0,2); eb2.parent=eb
p("bone collections attr:", hasattr(arm_data,"collections"))
coll=arm_data.collections.new("Body"); coll.assign(arm_data.edit_bones["root"])
p("collection assign ok:", [c.name for c in arm_data.collections], "is_visible:", coll.is_visible)
# bone color
em=arm_data.edit_bones["root"].color
p("edit_bone.color attrs:", [a for a in dir(em) if not a.startswith("_")])
try:
    em.palette="THEME04"; p("edit bone color set ok", em.palette)
except Exception as e: p("edit bone color err", repr(e))
bpy.ops.object.mode_set(mode='OBJECT')
b=arm_data.bones['root']
p("Bone.color:", [a for a in dir(b.color) if not a.startswith('_')], "palette:", b.color.palette)
try:
    b.color.palette='THEME04'; p("bone color set ok ->", b.color.palette)
except Exception as e: p("bone color err", e)
# 2 custom shapes
cs=bpy.data.objects.new("WGT_x", None); cs.empty_display_type='CIRCLE'; sc.collection.objects.link(cs)
pb=arm.pose.bones['root']; pb.custom_shape=cs; pb.use_custom_shape_bone_size=False
pb.custom_shape_scale_xyz=(0.2,0.2,0.2); pb.custom_shape_translation=(0,0,0.5)
p("custom shape ok:", pb.custom_shape.name, tuple(pb.custom_shape_scale_xyz), pb.use_custom_shape_bone_size)
p("armature display:", arm_data.display_type, "pose_position:", arm_data.pose_position)
# 3 IK constraint
pb2=arm.pose.bones['child']
c=pb2.constraints.new('IK'); c.target=arm; c.subtarget='root'
p("IK props:", [a for a in ('chain_count','use_stretch','use_tail','pole_target','pole_angle','use_ik_limit_x','use_ik_limit_y','use_ik_limit_z','ik_stiffness_x','ik_stiffness_y','ik_stiffness_z') if hasattr(c,a)])
# 4 driver
pb['curl']=0.0
d=pb.driver_add("rotation_quaternion",0)
d.driver.type='SCRIPTED'
v=d.driver.variables.new(); v.name='c'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='pose.bones["root"]["curl"]'
d.driver.expression='c*0.0'
p("driver ok:", d.driver.expression, len(d.driver.variables))
# 5 actions/slots
ob=arm
ob.animation_data_create()
act=bpy.data.actions.new("TestAct")
ob.animation_data.action=act
p("slot after assign:", [ (s.identifier, s.target_id_type) for s in act.slots])
pb.rotation_mode='QUATERNION'
pb.rotation_quaternion=(1,0,0,0)
pb.keyframe_insert('rotation_quaternion', frame=1, group='root')
p("action layered:", act.is_action_layered, "slots:", len(act.slots), "layers:", len(act.layers))
try:
    p("legacy fcurves:", len(act.fcurves))
except Exception as e: p("fcurves err", e)
# find fcurves via slot channelbag
try:
    slot=act.slots[0]; layer=act.layers[0]; strip=layer.strips[0]
    cb=strip.channelbag(slot)
    p("channelbag fcurves:", len(cb.fcurves), cb.fcurves[0].data_path, cb.fcurves[0].array_index)
except Exception as e: p("channelbag err", repr(e))
# 6 NLA
tr=ob.animation_data.nla_tracks.new(); tr.name="TT"
st=tr.strips.new("S", 1, act)
p("nla strip:", st.name, st.frame_start, st.frame_end, "blend:", st.blend_type, "additive attr:", hasattr(st,'use_additive'), "slot attr:", hasattr(st,'action_slot'))
try:
    p("strip slot:", st.action_slot.identifier if st.action_slot else None)
except Exception as e: p("strip slot err", repr(e))
tr.mute=True
# 7 parent_set auto weights on a simple mesh
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,1))
me=bpy.context.object
me.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
try:
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    p("auto weights ok, vgroups:", [g.name for g in me.vertex_groups], "mods:", [m.type for m in me.modifiers], "parent:", me.parent.name if me.parent else None)
except Exception as e: p("auto weights err", repr(e))
am=[m for m in me.modifiers if m.type=='ARMATURE'][0]
p("preserve volume attr:", hasattr(am,'use_deform_preserve_volume'))
p("armature modifier props:", [a for a in dir(am) if 'preserve' in a or 'vertex' in a])
# 8 misc
p("version:", bpy.app.version, "driver ns:", hasattr(bpy.app,'driver_namespace'))
p("prefs addons key check skipped")
p("action assign prop:", [a for a in dir(ob.animation_data) if 'action' in a])
p("nla strip props subset:", [a for a in dir(st) if a in ('blend_type','use_auto_blend','extrapolation','influence','use_reverse','frame_end_ui','repeat','scale','action_frame_start','action_frame_end','use_sync_length','use_animated_influence')])
p("fmod types:", [t for t in bpy.types.FModifier.bl_rna.properties['type'].enum_items.keys()])
p("gltf op:", hasattr(bpy.ops.export_scene,'gltf'), "fbx op:", hasattr(bpy.ops.export_scene,'fbx'))
# bone matrix api
p("Bone has matrix_local:", hasattr(b, 'matrix_local'), "Pose has matrix:", hasattr(ob.pose.bones[0], 'matrix'), "convert_space:", hasattr(ob.convert_space,'__call__') or dir(ob).count('convert_space'))
print("\n".join(out))
