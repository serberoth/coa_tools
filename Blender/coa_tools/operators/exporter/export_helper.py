import bpy
from ... functions import *

def remove_base_sprite(obj):
    active_object = bpy.context.active_object
    bpy.context.scene.objects.active = obj
    obj.hide = False
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    verts = []

    if "coa_base_sprite" in obj.vertex_groups and obj.data.coa_hide_base_sprite:
        v_group_idx = obj.vertex_groups["coa_base_sprite"].index
        for i,vert in enumerate(obj.data.vertices):
            for g in vert.groups:
                if g.group == v_group_idx:
                    verts.append(bm.verts[i])
                    break

    bpy.ops.mesh.reveal()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')


    bmesh.ops.delete(bm,geom=verts,context=1)
    bm = bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene.objects.active = active_object