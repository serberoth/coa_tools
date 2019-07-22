import bpy
import os


class COATOOLS_OT_VersionConverter(bpy.types.Operator):
    bl_idname = "coa_tools.convert_version"
    bl_label = "Convert COA(2.79 to 2.80)"
    bl_description = "Convert blendfile from 2.79 to 2.80"
    bl_options = {"REGISTER"}


    @classmethod
    def poll(cls, context):
        return True

    def convert_properties(self):
        # convert meshes
        for mesh in bpy.data.meshes:
            for prop_name in mesh.keys():
                if "coa_" in prop_name and "coa_tools" not in prop_name:
                    prop_name_new = prop_name.split("coa_")[1]
                    mesh.coa_tools[prop_name_new] = mesh[prop_name]

        # convert objects
        for obj in bpy.data.objects:

            if "sprite_object" in obj:
                obj.coa_tools["sprite_object"] = True
                del obj["sprite_object"]
            for prop_name in obj.keys():
                if "coa_" in prop_name and "coa_tools" not in prop_name:
                    prop_name_new = prop_name.split("coa_")[1]
                    obj.coa_tools[prop_name_new] = obj[prop_name]
                    del obj[prop_name]

    def create_material(self, context, mesh, name="Sprite"):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.blend_method = "BLEND"
        node_tree = mat.node_tree
        output_node = None
        # cleanup node tree
        for node in mat.node_tree.nodes:
            if node.type != "OUTPUT_MATERIAL":
                mat.node_tree.nodes.remove(node)
            else:
                output_node = node
        # create all required nodes and connect them
        tex_node = node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.interpolation = "Closest"
        tex_node.image = bpy.data.images[name]

        bpy.ops.coa_tools.create_material_group()
        coa_node_tree = bpy.data.node_groups["COATools Material"]
        coa_node = node_tree.nodes.new("ShaderNodeGroup")
        coa_node.name = "COA Material"
        coa_node.label = "COA Material"
        coa_node.node_tree = coa_node_tree
        coa_node.inputs["Alpha"].default_value = 1.0
        coa_node.inputs["Modulate Color"].default_value = [1, 1, 1, 1]

        node_tree.links.new(coa_node.inputs["Texture Color"], tex_node.outputs["Color"], verify_limits=True)
        node_tree.links.new(coa_node.inputs["Texture Alpha"], tex_node.outputs["Alpha"], verify_limits=True)
        node_tree.links.new(coa_node.outputs["BSDF"], output_node.inputs["Surface"], verify_limits=True)

        # position nodes in node tree
        tex_node.location = (0, 0)
        coa_node.location = (280, 0)
        output_node.location = (460, 0)
        mesh.materials.append(mat)
        return mat

    def convert_materials(self, context):
        texture_dir_path = os.path.join(os.path.dirname(bpy.data.filepath), "sprites")
        bpy.ops.coa_tools.create_material_group()
        for mesh in bpy.data.meshes:
            for material_name in mesh.materials.keys():
                mat = mesh.materials[material_name]
                texture_path = os.path.join(texture_dir_path, material_name)
                if os.path.isfile(texture_path):
                    bpy.data.images.load(texture_path, check_existing=True)
                    bpy.data.materials.remove(mat, do_unlink=True, do_id_user=True, do_ui_user=True)
                    mesh.materials.clear()
                    self.create_material(context, mesh, material_name)

    def set_shading(self):
        bpy.context.scene.view_settings.view_transform = "Standard"
        for obj in bpy.data.objects:
            if "sprite_object" in obj.coa_tools:
                for screen in bpy.data.screens:
                    for area in screen.areas:
                        if area.type == "VIEW_3D":
                            area.spaces[0].shading.type = "RENDERED"
                break

    def execute(self, context):
        self.convert_properties()
        self.convert_materials(context)
        self.set_shading()
        return {"FINISHED"}