import bpy, bmesh, inspect
print(bmesh.ops.create_uvsphere.__doc__[:600], flush=True)
bm = bmesh.new()
try:
    r = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=1.0)
    print("radius ok", len(r["verts"]), flush=True)
except Exception as e:
    print("radius failed", e, flush=True)
    r = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, diameter=1.0)
    print("diameter ok", len(r["verts"]), flush=True)
bm.free()
m = bpy.data.meshes.new("m"); ob = bpy.data.objects.new("m", m); bpy.context.collection.objects.link(ob)
mod = ob.modifiers.new("R","REMESH")
print("remesh modes:", [i.identifier for i in mod.bl_rna.properties['mode'].enum_items], flush=True)
print("remesh props:", [p.identifier for p in mod.bl_rna.properties if not p.is_readonly][:20], flush=True)
print("decimate types:", [i.identifier for i in bpy.types.DecimateModifier.bl_rna.properties['decimate_type'].enum_items], flush=True)
