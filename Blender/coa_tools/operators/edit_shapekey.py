'''
Copyright (C) 2015 Andreas Esau
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
import bpy_extras
import bpy_extras.view3d_utils
from math import radians
import mathutils
from mathutils import Vector, Matrix, Quaternion, geometry
import math
import bmesh
from bpy.props import FloatProperty, IntProperty, BoolProperty, StringProperty, CollectionProperty, FloatVectorProperty, EnumProperty, IntVectorProperty
from .. functions import *

class LeaveSculptmode(bpy.types.Operator):
    bl_idname = "coa_tools.leave_sculptmode"
    bl_label = "Leave Sculptmode"
    bl_description = ""
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        obj = context.active_object
        if obj != None and obj.type == "MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
        return {"FINISHED"}
        

class EditShapekeyMode(bpy.types.Operator):
    bl_idname = "coa_tools.edit_shapekey"
    bl_label = "Edit Shapekey"
    bl_description = ""
    bl_options = {"REGISTER","UNDO"}

    def get_shapekeys(self,context):
        SHAPEKEYS = []
        SHAPEKEYS.append(("NEW_KEY","New Shapekey","New Shapekey","NEW",0))
        obj = context.active_object
        if obj.data.shape_keys != None:
            i = 0
            for i,shape in enumerate(obj.data.shape_keys.key_blocks):
                if i > 0:
                    SHAPEKEYS.append((shape.name,shape.name,shape.name,"SHAPEKEY_DATA",i+1))
                
        
        return SHAPEKEYS

    shapekeys = EnumProperty(name="Shapekey",items=get_shapekeys)
    shapekey_name = StringProperty(name="Name",default="New Shape")
    mode_init = StringProperty()
    obj_init = None
    armature = None
    sprite_object = None
    
    @classmethod
    def poll(cls, context):
        return True
    
    def check(self,context):
        return True
    
    def draw(self,context):
        layout = self.layout
        col = layout.column()
        col.prop(self,"shapekeys")
        if self.shapekeys == "NEW_KEY":
            col.prop(self,"shapekey_name")
        
    
    def invoke(self,context,event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def execute(self, context):
        obj = context.active_object
        self.sprite_object = get_sprite_object(obj)
        self.armature = get_armature(self.sprite_object)
        self.obj_init = context.active_object
        
        self.mode_init = obj.mode if obj.mode != "SCULPT" else "OBJECT"
        
        shape_name = self.shapekeys
        
        if self.shapekeys == "NEW_KEY":
            if obj.data.shape_keys == None:
                obj.shape_key_add(name="Basis", from_mix=False)
            shape = obj.shape_key_add(name=self.shapekey_name, from_mix=False)    
            shape_name = shape.name
        
        
        for i,shape in enumerate(obj.data.shape_keys.key_blocks):
            if shape.name == shape_name:
                obj.active_shape_key_index = i
                break
        obj.show_only_shape_key = True
        self.sprite_object.coa_edit_shapekey = True
        bpy.ops.object.mode_set(mode="SCULPT")
        
        if self.armature != None:
            self.armature.data.pose_position = "REST"
        
        for brush in bpy.data.brushes:
            if brush.sculpt_tool == "GRAB":
                context.scene.tool_settings.sculpt.brush = brush
                break
        
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
    
    def exit_mode(self,context,event,obj):
        
        self.sprite_object.coa_edit_shapekey = False
        context.scene.objects.active = self.obj_init
        
        bpy.ops.object.mode_set(mode=self.mode_init)
        self.obj_init.show_only_shape_key = False
        
        context.scene.objects.active = obj
        if self.armature != None:
            self.armature.data.pose_position = "POSE"
        return {"FINISHED"}
    
    def modal(self, context, event):
        obj = context.active_object
        
        if event.type in {"ESC"} or obj != self.obj_init or self.sprite_object.coa_edit_shapekey == False:
            return self.exit_mode(context,event,obj)
        
        return {"PASS_THROUGH"}