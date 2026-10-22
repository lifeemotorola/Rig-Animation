import bpy
th=bpy.context.preferences.themes[0]
s=th.bone_color_sets[0]
print("PROPS", [a for a in dir(s) if not a.startswith('_')])
for i,s in enumerate(th.bone_color_sets[:20]):
    r=s.normal
    print(i+1, s.name, tuple(round(v,2) for v in r))
