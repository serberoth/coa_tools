import bpy

class ToggleAnimationArea(bpy.types.Operator):
    bl_idname = "coa_tools.toggle_animation_area"
    bl_label = "Toggle Animation Area"
    bl_description = "Toggle Animation Editors"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True
    
    
    def split_area(self,context,type="DOPESHEET_EDITOR",direction="HORIZONTAL",reference_area=None,ratio=0.7):
        start_areas = context.screen.areas[:]

        override = bpy.context.copy()
        if reference_area != None:
            override["area"] = reference_area
        else:    
            override["area"] = context.area
            
        bpy.ops.screen.area_split(override,direction=direction,factor=ratio)    

        for area in context.screen.areas:
            if area not in start_areas:
                area.type = type
        return area
    
    def join_area(self,context,area1,area2):
        type = str(area2.type)
        x1=0
        y1=0
        x2=0
        y2=0

        x1 = area1.x
        y1 = area1.y
        x2 = area2.x
        y2 = area2.y

        bpy.ops.screen.area_join(min_x=x2,min_y=y2,max_x=x1,max_y=y1)       
        area2.type = "NLA_EDITOR"    
        area2.type = type
        
    def get_areas(self,context):
        view_3d = None
        dopesheet_editor = None
        graph_editor = None
        
        dopesheet_editors = []
        graph_editors = []
        
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                view_3d = area
            elif area.type == "DOPESHEET_EDITOR":    
                dopesheet_editors.append(area)
            elif area.type == "GRAPH_EDITOR":
                graph_editors.append(area)
        
        for d in dopesheet_editors:
            for g in graph_editors:
                if g.height == d.height and (g.x == view_3d.x or d.x == view_3d.x):
                    dopesheet_editor = d
                    graph_editor = g
        return [view_3d, dopesheet_editor, graph_editor]
                    
    def execute(self, context):
        
        area_3d = None
        area_dopesheet_editor = None
        area_graph_editor = None
        
        area_3d, area_dopesheet_editor, area_graph_editor = self.get_areas(context)
                    
        ### create animation area
        if area_dopesheet_editor == None and area_graph_editor == None:        
            area_dopesheet_editor = self.split_area(context,type="DOPESHEET_EDITOR",direction="HORIZONTAL",reference_area=context.area,ratio=0.7)
            area_graph_editor = self.split_area(context,type="GRAPH_EDITOR",direction="VERTICAL",reference_area=area_dopesheet_editor,ratio=0.7)
        ### join animation area        
        else:
            self.join_area(context,area_graph_editor,area_dopesheet_editor)
            self.join_area(context,area_dopesheet_editor,area_3d)                
        
        return {"FINISHED"}
        