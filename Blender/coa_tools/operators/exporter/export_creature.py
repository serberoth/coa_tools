
'''
Copyright (C) 2019 Andreas Esau
andreasesau@gmail.com

Created by Andreas Esau

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import bpy
import bmesh
import json
from bpy.props import FloatProperty, IntProperty, BoolProperty, StringProperty, CollectionProperty, FloatVectorProperty, EnumProperty, IntVectorProperty
from collections import OrderedDict
from ... functions import *
from . export_helper import *
import math
from mathutils import Vector,Matrix, Quaternion, Euler
import shutil
from . texture_atlas_generator import TextureAtlasGenerator
import zipfile

class Sprite:
    def __init__(self, mesh_object):
        self.context = bpy.context
        self.name = mesh_object.name
        self.slots = []
        self.object = self.create_sprite(mesh_object)

    def create_sprite(self, mesh_object):
        # duplicate original object
        sprite = mesh_object.copy()
        sprite.name = mesh_object.name + "_EXPORT"
        if mesh_object.coa_type == "SLOT":
            for slot in mesh_object.coa_slot:
                slot_data = {"slot": slot.mesh.copy(),
                             "start_pt_index": None,
                             "end_pt_index": None,
                             "start_index": None,
                             "end_index": None}
                self.slots.append(slot_data)
                sprite.data = slot_data["slot"]
        else:
            slot_data = {"slot": sprite.data.copy(),
                         "start_pt_index": None,
                         "end_pt_index": None,
                         "start_index": None,
                         "end_index": None}
            self.slots = [slot_data]
            sprite.data = slot_data["slot"]
        self.context.scene.objects.link(sprite)

        # cleanup basesprite
        for slot_data in self.slots:
            slot = slot_data["slot"]
            sprite.data = slot
            if len(sprite.data.vertices) > 4:
                remove_base_sprite(sprite)
        return sprite

    def delete_sprite(self, scene):
        scene.objects.unlink(self.object)
        bpy.data.objects(self.object, do_unlink=True)
        del self

class CreatureExport(bpy.types.Operator):
    bl_idname = "coa_tools.export_creature"
    bl_label = "Creature Export"
    bl_description = ""
    bl_options = {"REGISTER"}

    minify_json = BoolProperty(name="Minify Json", default=True, description="Writes Json data in one line to reduce export size.")
    export_path = StringProperty(name="Export Path", default="", description="Creature Export Path.")
    project_name = StringProperty(name="Project Name", default="", description="Creature Project Name")

    def __init__(self):
        self.json_data = self.setup_json_data()
        self.export_scale = 1.0
        self.sprite_object = None
        self.armature_orig = None
        self.armature = None
        self.sprite_data = None
        self.reduce_size = False
        self.scene = None
        self.init_bone_positions = {}
        self.bone_weights = {}

        self.export_progress_total = 0
        self.export_progress_current = 0


    def setup_json_data(self):
        json_data = OrderedDict()

        json_data["mesh"] = OrderedDict()
        json_data["mesh"]["points"] = []
        json_data["mesh"]["uvs"] = []
        json_data["mesh"]["indices"] = []
        json_data["mesh"]["regions"] = OrderedDict()

        json_data["skeleton"] = OrderedDict()
        json_data["animation"] = OrderedDict()
        json_data["uv_swap_items"] = OrderedDict()
        json_data["anchor_points_items"] = {"AnchorPoints": []}

        return json_data

    def create_cleaned_armature_copy(self, context, armature_orig):
        armature = armature_orig

        selected_objects = bpy.context.selected_objects[:]
        active_object = bpy.context.active_object
        for ob in selected_objects:
            ob.select = False
        context.scene.objects.active = armature
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in armature.data.edit_bones:
            self.init_bone_positions[bone.name] = {"head": Vector(bone.head), "tail": Vector(bone.tail)}

        bpy.ops.object.mode_set(mode="OBJECT")
        for ob in context.selected_objects:
            ob.select = False
        for ob in selected_objects:
            ob.select = True
        context.scene.objects.active = active_object
        return armature

    def prepare_armature_and_sprites_for_export(self, context, scene):
        # get sprite object, sprites and armature
        self.sprite_object = get_sprite_object(context.active_object)
        self.armature_orig = get_armature(self.sprite_object)

        # get sprites that get exported
        sprites = []
        sprite_object_children = get_children(context, self.sprite_object, [])
        for child in sprite_object_children:
            if child.type == "MESH":
                sprites.append(Sprite(child))
        sprites = sorted(sprites, key=lambda sprite: sprite.object.location[1], reverse=False)

        armature = self.create_cleaned_armature_copy(context, self.armature_orig)
        return sprites, armature

    def get_vertices_from_v_group(self, bm, obj, v_group="", vert_type="BMESH"): # vert_type = ["BMESH", "MESH"]
        vertices = []
        faces = []
        if v_group not in obj.vertex_groups:
            return vertices, faces

        group_index = obj.vertex_groups[v_group].index
        for bm_vert in bm.verts:
            vert = obj.data.vertices[bm_vert.index]
            for group in vert.groups:
                if group.group == group_index:
                    if vert_type == "BMESH":
                        vertices.append(bm_vert)
                    elif vert_type == "MESH":
                        vertices.append(vert)
        return vertices, faces

    def get_init_vert_pos(self, obj, vert):
        if obj.data.shape_keys:
            return obj.data.shape_keys.key_blocks[0].data[vert.index].co
        else:
            return vert.co

    def get_uv_from_vert_first(self, uv_layer, v):
        bpy.context.tool_settings.use_uv_select_sync = True
        for l in v.link_loops:
            uv_data = l[uv_layer]
            return uv_data.uv
        return None

    def get_sprite_data_by_name(self, name):
        sprite_name = name
        slot_index = 0
        if "_COA_SLOT_" in name:
            sprite_name = name.split("_COA_SLOT_")[0]
            slot_index = int(name.split("_COA_SLOT_")[1])
        for sprite in self.sprite_data:
            if sprite.name == sprite_name:
                return sprite, sprite.slots[slot_index]
        return None, None

    def get_bone_weight(self, obj, vert, bone):
        # check if weights are cached
        if obj.name in self.bone_weights:
            if bone.name in self.bone_weights[obj.name]:
                if str(vert.index) in self.bone_weights[obj.name][bone.name]:
                    return self.bone_weights[obj.name][bone.name][str(vert.index)]


        if bone.name not in obj.vertex_groups:
            return 0.0
        else:
            v_group = obj.vertex_groups[bone.name]
            for group in vert.groups:
                group_name = obj.vertex_groups[group.group].name

                if group_name == v_group.name:
                    self.bone_weights[obj.name] = {bone.name:{vert.index:group.weight}}
                    return group.weight
        return 0

    def lerp(self, val1, val2, interpolation):
        return val1 * (1 - interpolation) + val2 * interpolation

    def scale_verts_by_bone(self, pbone, armature, mesh_object, vert_co, weight=1.0):
        # verts = mesh_object.data.vertices
        bone = armature.data.bones[pbone.name]
        bone_head = self.init_bone_positions[bone.name]["head"]
        bone_tail = self.init_bone_positions[bone.name]["tail"]
        bone_axis_x = (bone_tail - bone_head).normalized().xz
        bone_axis_y = bone_axis_x.orthogonal().normalized()

        world_axis_x = Vector((bone_axis_x.dot(Vector((1, 0))), bone_axis_y.dot(Vector((1, 0)))))
        world_axis_y = Vector((bone_axis_x.dot(Vector((0, 1))), bone_axis_y.dot(Vector((0, 1)))))

        bone_system_origin = (mesh_object.matrix_world.inverted() * (armature.matrix_world * bone_head)).xz

        bone_scale = pbone.matrix.to_scale()
        bone_scale_2d = Vector(( self.lerp( 1.0, bone_scale.y, weight), self.lerp(1.0, bone_scale.x, weight) ))

        vert_delta_co = vert_co.xz
        vert_delta_co -= bone_system_origin
        vert_delta_co = Vector((bone_axis_x.dot(vert_delta_co), bone_axis_y.dot(vert_delta_co)))
        vert_delta_co = Vector((vert_delta_co.x * bone_scale_2d.x, vert_delta_co.y * bone_scale_2d.y))
        vert_delta_co = Vector((world_axis_x.dot(vert_delta_co), world_axis_y.dot(vert_delta_co)))
        vert_delta_co += bone_system_origin

        scaled_vert_co = Vector((vert_delta_co.x, 0, vert_delta_co.y))
        return scaled_vert_co

    def get_shapekey_vert_data(self, obj, verts):
        default_vert_positions = []
        verts = sorted(verts, key=lambda vert: vert.index, reverse=False)
        for i,vert in enumerate(verts):
            default_vert_positions.append(obj.matrix_world * vert.co)

        verts = []
        index = int(obj.active_shape_key_index)
        shape_key = obj.shape_key_add("tmp_mixed_mesh", from_mix=True)
        for i, vert in enumerate(default_vert_positions):
            # shapekey_vert = obj.matrix_world * shape_key.data[i].co
            shapekey_vert = shape_key.data[i].co
            for bone in self.armature.pose.bones:
                if bone.name in obj.vertex_groups:
                    bone_weight = self.get_bone_weight(obj, obj.data.vertices[i], bone)
                    scaled_vert = self.scale_verts_by_bone(bone, self.armature, obj, shapekey_vert, bone_weight)
                    shapekey_vert = scaled_vert
            shapekey_vert = obj.matrix_world * shapekey_vert

            relative_offset = (shapekey_vert - vert)
            verts.append(round(relative_offset.x, 3))
            verts.append(round(relative_offset.z, 3))
        obj.shape_key_remove(shape_key)
        obj.active_shape_key_index = index


        return verts

    def create_dupli_atlas_objects(self, context):
        atlas_objects = []

        # deselect any selected object
        for ob in bpy.context.selected_objects:
            ob.select = False

        for sprite in self.sprite_data:
            meshes = []
            for i, slot_data in enumerate(sprite.slots):
                slot = slot_data["slot"]
                atlas_sprite = sprite.object.copy()
                atlas_sprite.data = slot.copy()
                context.scene.objects.link(atlas_sprite)
                atlas_sprite.select = True
                context.scene.objects.active = atlas_sprite
                name = sprite.name + "_COA_SLOT_" + str(i).zfill(3) if len(sprite.slots) > 1 else sprite.name
                meshes.append({"obj": atlas_sprite, "name": name})
                atlas_sprite["coa_sprite_object_name"] = sprite.object.name

            for mesh_data in meshes:
                atlas_sprite = mesh_data["obj"]
                name = mesh_data["name"]
                for v_group in atlas_sprite.vertex_groups:
                    # atlas_sprite.vertex_groups.remove(v_group)
                    if v_group.name not in self.armature.data.bones:
                        atlas_sprite.vertex_groups.remove(v_group)
                    else:
                        v_group.name = "BONE_VGROUP_" + v_group.name
                verts = []
                for vert in atlas_sprite.data.vertices:
                    verts.append(vert.index)
                v_group = atlas_sprite.vertex_groups.new(name)
                v_group.add(verts, 1.0, "ADD")
                atlas_objects.append(atlas_sprite)

        # select newely created objects
        for ob in atlas_objects:
            ob.select = True
            context.scene.objects.active = ob
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')
            bpy.ops.object.mode_set(mode="OBJECT")
        return atlas_objects

    def get_uv_dimensions(self, bm, verts, uv_layer):
        ### first get the total dimensions of the uv
        left = 0
        top = 0
        bottom = 1
        right = 1
        for vert in verts:
            uv_first = self.get_uv_from_vert_first(uv_layer, vert)
            for i, val in enumerate(uv_first):
                if i == 0:
                    left = max(left, val)
                    right = min(right, val)
                else:
                    top = max(top, val)
                    bottom = min(bottom, val)
        height = top - bottom
        width = left - right
        return {"width":width, "height":height}

    def create_mesh_data(self, context, merged_atlas_obj):
        points = []
        uvs = []
        indices = []

        context.scene.objects.active = merged_atlas_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')

        current_face_index = 0
        for v_group in merged_atlas_obj.vertex_groups:
            if "BONE_VGROUP_" not in v_group.name:
                bm = bmesh.from_edit_mesh(merged_atlas_obj.data)
                # bm.verts.index_update()
                # bm.faces.index_update()

                sprite, slot = self.get_sprite_data_by_name(v_group.name)

                uv_layer = bm.loops.layers.uv.active
                vertices, faces = self.get_vertices_from_v_group(bm, merged_atlas_obj, v_group.name)
                vertices.sort(key=lambda v: v.index)

                start_pt_index = float("inf")
                end_pt_index = 0

                uv_dimensions = self.get_uv_dimensions(bm, vertices, uv_layer)
                merged_atlas_obj[v_group.name] = uv_dimensions

                for i, vert in enumerate(vertices):
                    # get region index
                    start_pt_index = min(vert.index, start_pt_index)
                    end_pt_index = max(vert.index, end_pt_index)
                    slot["start_pt_index"] = start_pt_index
                    slot["end_pt_index"] = end_pt_index

                    # get point data
                    # coords = mathutils.Vector(merged_atlas_obj.matrix_world * vert.co).xzy
                    coords = mathutils.Vector(merged_atlas_obj.matrix_world * self.get_init_vert_pos(merged_atlas_obj, vert)).xzy
                    points.append(round(coords.x, 3))
                    points.append(round(coords.y, 3))

                    # get uv data
                    uv = self.get_uv_from_vert_first(uv_layer, vert)
                    uvs.append(round(uv[0], 3))
                    uvs.append(round(uv[1] + 1 - uv[1]*2, 3))

                # get indices data
                for i, face in enumerate(bm.faces):
                    if i == 0:
                        slot["start_index"] = current_face_index
                    for vert in face.verts:
                        slot["end_index"] = current_face_index
                        current_face_index += 1
                        indices.append(vert.index)

        bpy.ops.object.mode_set(mode="OBJECT")
        return points, uvs, indices

    def create_region_data(self, context, merged_atlas_obj):
        regions = OrderedDict()

        context.scene.objects.active = merged_atlas_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(merged_atlas_obj.data)

        region_id = 0
        for sprite in self.sprite_data:
            for i, slot in enumerate(sprite.slots):
                sprite.object.data = slot["slot"]
                name = sprite.name if len(sprite.slots) <= 1 else sprite.name + "_" + str(i).zfill(3)
                regions[name] = OrderedDict()
                regions[name]["start_pt_index"] = slot["start_pt_index"]
                regions[name]["end_pt_index"] = slot["end_pt_index"]
                regions[name]["start_index"] = slot["start_index"]
                regions[name]["end_index"] = slot["end_index"]
                regions[name]["id"] = region_id
                regions[name]["weights"] = OrderedDict()

                # get root bone weights
                for vert in slot["slot"].vertices:
                    if "Root" not in regions[name]["weights"]:
                        regions[name]["weights"]["Root"] = []
                    regions[name]["weights"]["Root"].append(0)

                slot_name = sprite.name + "_COA_SLOT_" + str(i).zfill(3) if len(sprite.slots) > 1 else sprite.name
                vertices, faces = self.get_vertices_from_v_group(bm, merged_atlas_obj, slot_name, vert_type="MESH")

                for bone in self.armature.data.bones:
                    bone_v_group_name = "BONE_VGROUP_"+bone.name
                    regions[name]["weights"][bone.name] = []
                    for i, vert in enumerate(vertices):
                        regions[name]["weights"][bone.name].append(0)
                        for group in vert.groups:
                            v_group_name = merged_atlas_obj.vertex_groups[group.group].name
                            if v_group_name == bone_v_group_name:
                                vert_index = vert.index - slot["start_pt_index"]
                                regions[name]["weights"][bone.name][vert_index] = round(max(group.weight, 0.06), 3)

                region_id += 1
        bpy.ops.object.mode_set(mode="OBJECT")
        return regions

    def create_skeleton_data(self):
        self.armature.data.pose_position = "REST"
        bpy.context.scene.update()
        skeleton = OrderedDict()
        for i, pbone in enumerate(self.armature.pose.bones):
            pbone["id"] = i+1

        skeleton["Root"] = OrderedDict()
        skeleton["Root"]["name"] = "Root"
        skeleton["Root"]["id"] = 0
        skeleton["Root"]["restParentMat"] = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        skeleton["Root"]["localRestStartPt"] = [-1, 0]
        skeleton["Root"]["localRestEndPt"] = [0, 0]
        skeleton["Root"]["children"] = []
        for pbone in self.armature.pose.bones:
            if pbone.parent == None:
                skeleton["Root"]["children"].append(pbone["id"])


        for pbone in self.armature.pose.bones:
            skeleton[pbone.name] = OrderedDict()
            skeleton[pbone.name]["name"] = pbone.name
            skeleton[pbone.name]["id"] = pbone["id"]
            skeleton[pbone.name]["restParentMat"] = self.get_bone_parent_mat(pbone)
            head = self.get_bone_head_tail(pbone)["head"]
            tail = self.get_bone_head_tail(pbone)["tail"]
            skeleton[pbone.name]["localRestStartPt"] = [round(head.x, 3), round(head.y, 3)]
            skeleton[pbone.name]["localRestEndPt"] = [round(tail.x, 3), round(tail.y, 3)]
            skeleton[pbone.name]["children"] = []
            for child in pbone.children:
                skeleton[pbone.name]["children"].append(child["id"])
        self.armature.data.pose_position = "POSE"
        return skeleton

    # gets head and tail of a bone in either normal or local space of it's parent bone
    def get_bone_head_tail(self, pbone, local=True):
        parent_x_axis = Vector((1, 0))
        parent_y_axis = Vector((0, 1))
        space_origin = Vector((0, 0))
        if pbone.parent != None and local:
            parent_x_axis = (pbone.parent.tail.xz - pbone.parent.head.xz).normalized()
            parent_y_axis = parent_x_axis.orthogonal().normalized()
            space_origin = pbone.parent.tail.xz

        head = pbone.head.xz - space_origin
        tail = pbone.tail.xz - space_origin

        local_tail_x = round(tail.dot(parent_x_axis), 3)
        local_tail_y = round(tail.dot(parent_y_axis), 3)

        local_head_x = round(head.dot(parent_x_axis), 3)
        local_head_y = round(head.dot(parent_y_axis), 3)

        return {"head": Vector((local_head_x, local_head_y)), "tail": Vector((local_tail_x, local_tail_y))}

    def get_bone_parent_mat(self, pbone):
        if pbone.parent == None:
            return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        else:
            matrix_array = []
            for row in pbone.parent.matrix.row:
                for value in row:
                    matrix_array.append(round(value, 3))
            return matrix_array

    def bone_is_keyed_on_frame(self, bone, frame, animation_data, type="LOCATION"):  ### LOCATION, ROTATION, SCALE, ANY
        action = animation_data.action if animation_data != None else None
        type = "." + type.lower()
        if action != None:
            for fcurve in action.fcurves:
                if bone.name in fcurve.data_path and (type in fcurve.data_path or type == ".any"):
                    for keyframe in fcurve.keyframe_points:
                        if keyframe.co[0] == frame:
                            return True
        return False

    def create_animation_data(self, context):
        animation = OrderedDict()
        anim_collections = self.sprite_object.coa_anim_collections
        for anim_index, anim in enumerate(anim_collections):
            if anim.name not in ["NO ACTION", "Restpose"]:
                self.sprite_object.coa_anim_collections_index = anim_index  ### set animation

                animation[anim.name] = OrderedDict()
                animation[anim.name]["bones"] = OrderedDict()
                animation[anim.name]["meshes"] = OrderedDict()
                animation[anim.name]["uv_swaps"] = OrderedDict()
                animation[anim.name]["mesh_opacities"] = OrderedDict()

                for frame in range(anim.frame_end+1):
                    self.export_progress_current += 1
                    current_progress = self.export_progress_current/self.export_progress_total
                    context.window_manager.progress_update(current_progress)
                    context.scene.frame_set(frame)
                    context.scene.update()

                    # bone relevant data
                    for pbone in self.armature.pose.bones:
                        start_pt = self.get_bone_head_tail(pbone, local=False)["head"]
                        end_pt = self.get_bone_head_tail(pbone, local=False)["tail"]

                        bake_animation = self.scene.coa_export_bake_anim and  frame%self.scene.coa_export_bake_steps == 0
                        # if self.bone_is_keyed_on_frame(pbone, frame, self.armature.animation_data, type="ANY") or frame == 0 or frame == anim.frame_end or bake_animation: # remove baking for now
                        if str(frame) not in animation[anim.name]["bones"]:
                            animation[anim.name]["bones"][str(frame)] = OrderedDict()
                        animation[anim.name]["bones"][str(frame)][pbone.name] = {"start_pt": [round(start_pt.x, 3), round(start_pt.y, 3)],
                                                                                 "end_pt": [round(end_pt.x, 3), round(end_pt.y, 3)]}
                    # mesh relevant data
                    animation[anim.name]["meshes"][str(frame)] = OrderedDict()
                    animation[anim.name]["uv_swaps"][str(frame)] = OrderedDict()
                    animation[anim.name]["mesh_opacities"][str(frame)] = OrderedDict()
                    for sprite in self.sprite_data:
                        sprite_object = bpy.data.objects[sprite.name]
                        # collect shapekey animation
                        local_displacements = self.get_shapekey_vert_data(sprite.object, sprite.object.data.vertices)
                        animation[anim.name]["meshes"][str(frame)][sprite.name] = {"use_dq": True, "use_local_displacements": True, "use_post_displacements": False, "local_displacements":local_displacements}
                        # animation[anim.name]["meshes"][str(frame)][sprite.name] = {"use_dq": True, "use_local_displacements": False, "use_post_displacements": False}

                        # collect slot swapping data
                        animation[anim.name]["uv_swaps"][str(frame)][sprite.name] = {"local_offset": [0, 0], "global_offset": [0, 0], "scale": [-1, -1]}

                        # collect mesh opacity and tint data
                        animation[anim.name]["mesh_opacities"][str(frame)][sprite.name] = {"opacity": round(sprite_object.coa_alpha*100, 1)}

        return animation

    def write_json_file(self):
        # get export, project and json path
        export_path = bpy.path.abspath(self.scene.coa_export_path)
        json_path = os.path.join(export_path, self.project_name + "_data.json")
        zip_path = os.path.join(export_path, self.project_name + "_data.zip")

        # write json file
        if self.reduce_size:
            json_file = json.dumps(self.json_data, separators=(',', ':'))
        else:
            json_file = json.dumps(self.json_data, indent="  ", sort_keys=False)

        text_file = open(json_path, "w")
        text_file.write(json_file)
        text_file.close()

        zip_file = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
        zip_file.write(json_path, os.path.basename(json_path))
        zip_file.close()

    def save_texture_atlas(self, context, img_atlas, img_path, atlas_name):
        compression_rate = int(context.scene.render.image_settings.compression)
        context.scene.render.image_settings.compression = 100
        texture_path = os.path.join(img_path, atlas_name + "_atlas.png")
        img_atlas.save_render(texture_path)
        context.scene.render.image_settings.compression = compression_rate

    def setup_progress(self, context):
        self.export_progress_total = 0
        self.export_progress_current = 0
        for i, anim in enumerate(self.sprite_object.coa_anim_collections):
            if anim.name not in ["Restpose", "NO ACTION"]:
                self.export_progress_total += anim.frame_end + 1
        context.window_manager.progress_begin(0, 100)
        context.window_manager.progress_update(0)

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        self.reduce_size = context.scene.coa_minify_json
        bpy.ops.ed.undo_push(message="Start Export")
        bpy.ops.ed.undo_push(message="Start Export")
        self.json_data = self.setup_json_data()
        self.scene = context.scene

        scene = context.scene

        self.export_scale = 1 / get_addon_prefs(context).sprite_import_export_scale
        self.sprite_scale = self.scene.coa_sprite_scale
        self.sprite_data, self.armature = self.prepare_armature_and_sprites_for_export(context, scene)
        self.setup_progress(context)
        for ob in context.scene.objects:
            ob.select = False
        atlas_objects = self.create_dupli_atlas_objects(context)

        img_atlas, merged_atlas_obj, atlas = TextureAtlasGenerator.generate_uv_layout(name="COA_UV_ATLAS", objects=atlas_objects, width=128,
                                                 height=128, max_width=2048, max_height=2048, margin=1,
                                                 texture_bleed=0, square=False, output_scale=self.sprite_scale)
        self.save_texture_atlas(context, img_atlas, self.export_path, self.project_name)



        points, uvs, indices = self.create_mesh_data(context, merged_atlas_obj)
        self.json_data["mesh"]["points"] = points
        self.json_data["mesh"]["uvs"] = uvs
        self.json_data["mesh"]["indices"] = indices
        self.json_data["mesh"]["regions"] = self.create_region_data(context, merged_atlas_obj)
        self.json_data["skeleton"] = self.create_skeleton_data()
        self.json_data["animation"] = self.create_animation_data(context)

        self.write_json_file()

        # cleanup scene and add an undo history step
        bpy.ops.ed.undo()
        bpy.ops.ed.undo_push(message="Export Creature")
        self.report({"INFO"}, "Export successful.")

        context.window_manager.progress_end()
        return {"FINISHED"}
