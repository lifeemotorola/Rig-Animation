import bpy
out=[]
def p(*a): out.append(" ".join(str(x) for x in a))
sc=bpy.context.scene
ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
b1=ad.edit_bones.new("upper_arm.L"); b1.head=(0,0,0); b1.tail=(0,0,1)
b2=ad.edit_bones.new("forearm.L"); b2.head=(0,0,1); b2.tail=(0,0,2); b2.parent=b1
bpy.ops.object.mode_set(mode='POSE')
c=arm.pose.bones["upper_arm.L"].constraints.new('COPY_ROTATION'); c.target=arm; c.subtarget="forearm.L"
fc=arm.pose.bones["upper_arm.L"].driver_add('rotation_quaternion',0)
v=fc.driver.variables.new(); v.type='TRANSFORMS'; v.targets[0].id=arm; v.targets[0].bone_target="forearm.L"
bpy.ops.object.mode_set(mode='OBJECT')
me=bpy.data.meshes.new("M"); ob=bpy.data.objects.new("M",me); sc.collection.objects.link(ob)
ob.vertex_groups.new(name="forearm.L")
ad.bones["forearm.L"].name="lower_arm.L"
p("constraint subtarget after rename:", c.subtarget)
p("driver bone_target after rename:", v.targets[0].bone_target)
p("vertex group after rename:", [g.name for g in ob.vertex_groups])
# id properties ui
arm["testprop"]=0.5
try:
    arm.id_properties_ui("testprop").update(min=0.0,max=1.0,soft_min=0.0,soft_max=1.0,description="d")
    p("id_properties_ui ok", arm.id_properties_ui("testprop").as_dict().get('min'))
except Exception as e: p("id props ui err", repr(e))
# pose bone id props ui
pb=arm.pose.bones["upper_arm.L"]; pb["curl"]=0.0
try:
    pb.id_properties_ui("curl").update(min=0,max=1); p("posebone idprops ui ok")
except Exception as e: p("pb idprops err", repr(e))
# bake op introspection
rp=bpy.ops.nla.bake.get_rna_type().properties
p("bake props:", sorted([x.identifier for x in rp if x.identifier not in ('rna_type',)]))
# armature select all bone ops
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')
p("selected bones:", [b.name for b in arm.pose.bones if b.select])
p("pose copy/paste ops:", hasattr(bpy.ops.pose,'copy'), hasattr(bpy.ops.pose,'paste'))
p("nla bake exists:", hasattr(bpy.ops.nla,'bake'))
try:
    p("poselib ops:", [o for o in dir(bpy.ops.poselib) if not o.startswith('_')][:8])
except Exception as e: p("poselib err", repr(e))
# action frame range
act=bpy.data.actions.new("X"); p("action props:", [a for a in ('frame_range','frame_start','frame_end','use_frame_range','use_cyclic') if hasattr(act,a)])
p("slots api:", [a for a in dir(bpy.types.ActionSlots) if not a.startswith('_')])
p("ActionSlot props:", [a for a in dir(bpy.types.ActionSlot) if not a.startswith('_')])
p("strip action_slot set ok:", hasattr(bpy.types.NlaStrip,'action_slot'))

p("mesh eval ok")
# material / color attribute for demo later
p("mathutils.noise:", __import__('mathutils').noise.noise_vector((0.1,0.2,0.3)))
p("smoothstep available?", hasattr(__import__('mathutils').noise,'noise'))
print("\n".join(out))
