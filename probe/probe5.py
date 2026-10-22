import bpy
th=bpy.context.preferences.themes[0]
for i in range(20):
    s=th.bone_color_sets[i]
    print(i+1, tuple(round(v,2) for v in s.normal), flush=True)
