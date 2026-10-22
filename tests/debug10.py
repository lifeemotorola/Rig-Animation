import bpy, sys
from mathutils import Vector
sys.path.insert(0,'/home/user')

def make(stretch, chain, ik_target_same_arm=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ad=bpy.data.armatures.new("A"); arm=bpy.data.objects.new("A",ad); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    e_pelvis=ad.edit_bones.new("pelvis"); e_pelvis.head=(0,0.013,0.899); e_pelvis.tail=(0,0.01,1.108)
    e_spine=ad.edit_bones.new("spine"); e_spine.head=(0,0.01,1.108); e_spine.tail=(0,0.0,1.31); e_spine.parent=e_pelvis; e_spine.use_connect=True
    e_chest=ad.edit_bones.new("chest"); e_chest.head=(0,0,1.31); e_chest.tail=(0,0,1.5); e_chest.parent=e_spine; e_chest.use_connect=True
    e_clav=ad.edit_bones.new("clav"); e_clav.head=(0.03,0,1.45); e_clav.tail=(0.14,0,1.45); e_clav.parent=e_chest
    e_up=ad.edit_bones.new("upper"); e_up.head=(0.14,0,1.45); e_up.tail=(0.37,0,1.2); e_up.parent=e_clav; e_up.use_connect=True
    e_fore=ad.edit_bones.new("fore"); e_fore.head=(0.37,0,1.2); e_fore.tail=(0.6,0,0.95); e_fore.parent=e_up; e_fore.use_connect=True
    e_ctl=ad.edit_bones.new("ctl"); e_ctl.head=(0.6,0,0.95); e_ctl.tail=(0.7,0,0.85)
    bpy.ops.object.mode_set(mode='OBJECT')
    c=arm.pose.bones["fore"].constraints.new('IK'); c.target=arm; c.subtarget="ctl"; c.chain_count=chain; c.use_stretch=stretch
    bpy.context.view_layer.update()
    return arm

for stretch, chain in ((True,2),(False,2),(True,1)):
    arm=make(stretch,chain)
    print(f"stretch={stretch} chain={chain} spine head={tuple(round(v,3) for v in arm.pose.bones['spine'].head)} rest={tuple(round(v,3) for v in arm.data.bones['spine'].head_local)}", flush=True)
