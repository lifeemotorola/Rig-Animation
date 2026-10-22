import bpy
out=[]
def p(*a): out.append(" ".join(str(x) for x in a))
sc=bpy.context.scene
arm_data=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",arm_data)
sc.collection.objects.link(arm); bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
names=["root","thigh.L","shin.L","foot.L","toe.L"]
prev=None
for i,n in enumerate(names):
    eb=arm_data.edit_bones.new(n); eb.head=(0,0,-i*0.4); eb.tail=(0,0,-(i+1)*0.4)
    if prev: eb.parent=prev; eb.use_connect=True
    prev=eb
eb=arm_data.edit_bones["thigh.L"]
p("eb props:", {a:getattr(eb,a) for a in ('inherit_scale','use_inherit_rotation','use_local_location','use_deform','bbone_segments') if hasattr(eb,a)})
p("inherit_scale enum:", [e.identifier for e in eb.bl_rna.properties['inherit_scale'].enum_items])
p("bbone_x available:", hasattr(eb,'bbone_x'), "use_connect:", eb.use_connect)
bpy.ops.object.mode_set(mode='POSE')
pb=arm.pose.bones["shin.L"]
p("PoseBone ik props:", [a for a in dir(pb) if 'ik_' in a])
p("PoseBone refs:", [a for a in dir(pb) if a in ('bbone_segments','rotation_mode','lock_rotation','use_ik_limit_x','ik_stiffness_x','ik_limit_x')])
bpy.ops.object.mode_set(mode='OBJECT')
# fcurve direct creation through channelbag
ob=arm; ob.animation_data_create()
act=bpy.data.actions.new("Direct")
ob.animation_data.action=act
p("slots after assign empty count:", len(act.slots))
bpy.ops.object.mode_set(mode='POSE')
pb=arm.pose.bones["thigh.L"]; pb.rotation_mode='QUATERNION'; pb.keyframe_insert('rotation_quaternion',frame=1)
bpy.ops.object.mode_set(mode='OBJECT')
slot=act.slots[0]; layer=act.layers[0]; strip=layer.strips[0]; cb=strip.channelbag(slot)
p("cb fcurves:", [(f.data_path,f.array_index) for f in cb.fcurves])
try:
    nf=cb.fcurves.new('pose.bones["shin.L"].rotation_quaternion', index=0)
    nf.keyframe_points.add(3)
    import numpy as np
    co=np.array([1,1.0, 5,1.0, 9,1.0])
    nf.keyframe_points.foreach_set('co', co)
    nf.update()
    p("direct fcurve ok keys:", len(nf.keyframe_points))
except Exception as e: p("direct fcurve err", repr(e))
# slot explicit creation + assignment
try:
    s2=act.slots.new(id_type='OBJECT', name="Other"); p("slot new ok:", s2.identifier, s2.name_display)
    ob.animation_data.action_slot=s2; p("assigned slot:", ob.animation_data.action_slot.identifier)
except Exception as e: p("slot new err", repr(e))
# NLA blend enum
p("nla blend enum:", [e.identifier for e in bpy.types.NlaStrip.bl_rna.properties['blend_type'].enum_items])
p("nla extrapolate enum:", [e.identifier for e in bpy.types.NlaStrip.bl_rna.properties['extrapolation'].enum_items])
# Multi-slot action into NLA
bpy.ops.object.mode_set(mode='POSE'); pb.keyframe_insert('rotation_quaternion',frame=1); bpy.ops.object.mode_set(mode='OBJECT')
act2=ob.animation_data.action
p("nla add multi:")
tr=ob.animation_data.nla_tracks.new()
try:
    st=tr.strips.new("S2",1,act2); p("ok", st.action_slot.identifier if st.action_slot else None)
except Exception as e: p("err", repr(e))
# constraint influence driver
bpy.ops.object.mode_set(mode='POSE')
c=arm.pose.bones["shin.L"].constraints.new('COPY_ROTATION')
p("copyrot props:", {a:getattr(c,a) for a in ('target_space','owner_space','mix_mode') if hasattr(c,a)})
p("mix enum:", [e.identifier for e in c.bl_rna.properties['mix_mode'].enum_items])
p("space enum:", [e.identifier for e in c.bl_rna.properties['owner_space'].enum_items])
fc=c.driver_add("influence"); fc.driver.type='SCRIPTED'
arm["curl"]=0.5
v=fc.driver.variables.new(); v.name='c'; v.type='SINGLE_PROP'; v.targets[0].id=arm; v.targets[0].data_path='["curl"]'
fc.driver.expression='c'
p("influence driver ok:", fc.driver.expression, len(fc.driver.variables))
bpy.ops.object.mode_set(mode='OBJECT')
# collection exclude
c2=bpy.data.collections.new("WGT"); sc.collection.children.link(c2)
lc=bpy.context.view_layer.layer_collection.children["WGT"]; lc.exclude=True
p("exclude ok:", lc.exclude)
# drivers on posebone rotation vs action conflict sanity
p("driver namespace attrs ok:", hasattr(bpy.app,'driver_namespace'))
# text/mesh/curve creation
me=bpy.data.meshes.new("W"); me.from_pydata([(0,0,0),(1,0,0),(1,1,0)],[ (0,1),(1,2),(2,0)],[]); me.update()
p("mesh edges:", len(me.edges), "verts:", len(me.vertices))
cu=bpy.data.curves.new("TW","CURVE"); cu.dimensions='3D'; sp=cu.splines.new('POLY'); sp.points.add(3); sp.points.foreach_set('co',[0,0,0,1, 1,0,0,1, 2,0,0,1, 3,0,0,1]); p("curve pts:", len(sp.points))
# gp? skip
p("obj props:", [a for a in ('show_in_front','display_type','hide_viewport','hide_render') if hasattr(arm,a)])
p("edit_bone color palette enum sample:", [e.identifier for e in bpy.types.BoneColor.bl_rna.properties['palette'].enum_items][:6])
p("armature display enum:", [e.identifier for e in bpy.types.Armature.bl_rna.properties['display_type'].enum_items])
print("\n".join(out))
