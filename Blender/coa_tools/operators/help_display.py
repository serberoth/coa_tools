import bpy
import blf, bgl


class ShowHelp(bpy.types.Operator):
    bl_idname = "coa_tools.show_help"
    bl_label = "Show Help"
    bl_description = "Show Help"
    bl_options = {"REGISTER"}

    region_offset = 0
    region_height = 0
    _timer = None
    alpha = 1.0
    alpha_current = 0.0
    global_pos = 0.0
    i = 0
    fade_in = False
    scale = .7
    @classmethod
    def poll(cls, context):
        return True

    def write_text(self,text,size=20,pos_y=0,color=(1,1,1,1)):
        start_pos = self.region_height - 60*self.scale
        lines = text.split("\n")
        
        pos_y = start_pos - (pos_y * self.scale)
        size = int(size * self.scale)
        
        bgl.glColor4f(color[0],color[1],color[2],color[3]*self.alpha_current)
        line_height = (size + size*.5) * self.scale
        for i,line in enumerate(lines):
            
            blf.position(self.font_id, 15+self.region_offset, pos_y-(line_height*i), 0)
            blf.size(self.font_id, size, 72)
            blf.draw(self.font_id, line)
            
    def invoke(self, context, event):
        wm = context.window_manager
        wm.coa_show_help = True
        args = ()
        self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback_px, args, "WINDOW", "POST_PIXEL")
        self._timer = wm.event_timer_add(0.1, context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}
    
    def fade(self):
        self.alpha_current = self.alpha_current*.55 + self.alpha*.45
            
    def modal(self, context, event):
        wm = context.window_manager
        context.area.tag_redraw()
        for region in context.area.regions:
            if region.type == "TOOLS":
                self.region_offset = region.width
            if region.type == "WINDOW":    
                self.region_height = region.height
                self.scale = self.region_height/920
                self.scale = min(1.0,max(.7,self.scale))
        
        if context.user_preferences.system.use_region_overlap:
            pass
        else:
            self.region_offset = 0
        
        if not wm.coa_show_help:
            self.alpha = 0.0
            
        if not wm.coa_show_help and round(self.alpha_current,1) == 0:#event.type in {"RIGHTMOUSE", "ESC"}:
            return self.finish()
        
        if self.alpha != round(self.alpha_current,1):
            self.fade()  
        return {"PASS_THROUGH"}

    def finish(self):
        context = bpy.context
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, "WINDOW")
        
        return {"FINISHED"}

    def draw_callback_px(self):
        self.font_id = 0  # XXX, need to find out how best to get this.
        global_pos = self.region_height - 60
        # draw some text
        headline_color = [1.0, 0.9, 0.6, 1.0]
        
        ### draw gradient overlay
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBegin(bgl.GL_QUAD_STRIP)
        color_black = [0.0,0.0,0.0]
        x_coord1 = self.region_offset
        x_coord2 = 525
        y_coord1 = self.region_height
        alpha1 = self.alpha_current * 0.7
        alpha2 = self.alpha_current * 0.0
        
        bgl.glColor4f(color_black[0],color_black[1],color_black[2],alpha1)
        bgl.glVertex2f(x_coord1,0)
        
        bgl.glColor4f(color_black[0],color_black[1],color_black[2],alpha1)
        bgl.glVertex2f(x_coord1,y_coord1)
        
        bgl.glColor4f(color_black[0],color_black[1],color_black[2],alpha2)
        bgl.glVertex2f(x_coord2,0)
        
        bgl.glColor4f(color_black[0],color_black[1],color_black[2],alpha2)
        bgl.glVertex2f(x_coord2,y_coord1)
        bgl.glEnd()
        
        
        
        ### draw hotkeys help
        texts = [
                ["Hotkeys - Object Mode",20],
                ["   F   -   Contextual Pie Menu",15],
                ["Hotkeys - Object Outliner",20],
                ["   Ctrl + Click    -   Add Item to Selection",15],
                ["   Shift + Click   -   Multi Selection",15],
                ["Hotkeys - Keyframing",20],
                ["   Ctrl + Click on Key Operator    -   Opens Curve Interpolation Options",15],
                ["   I    -   Keyframe Menu",15],
                ["Hotkeys - Edit Armature Mode",20],
                ["   Click + Drag    -   Draw Bone",15],
                ["   Shift + Click + Drag    -   Draw Bone locked to 45 Angle",15],
                ["   Alt + Click    -    Bind Sprite to selected Bones",15],
                ["   ESC/Tab    -    Exit Armature Mode",15],
                ["Hotkeys - Edit Mesh Mode",20],
                ["   Click + Drag    -   Draw Vertex Contour",15],
                ["   K   -   Knife Tool",15],
                ["   L   -   Select Mesh",15],
                ["   Alt + Click on Vertex   -   Close Contour",15],
                ["   ESC/Tab    -    Exit Mesh Mode",15],
                ["",15],
                ["   W    -    Specials Menu",15],
                ["   Ctrl + V    -    Vertex Menu",15],
                ["   Ctrl + E    -    Edge Menu",15],
                ["   Ctrl + F    -    Face Menu",15],
                ["Hotkeys - Blender General",20],
                ["   A   -   Select / Deselect All",15],
                ["   B   -   Border Selection",15],
                ["   C   -   Paint Selection",15],
                ["   S   -   Scale Selection",15],
                ["   G   -   Move Selection",15],
                ["   R   -   Rotate Selection",15],
                ["",15],
                ["   W   -   Specials Menu",15]
                ]
        
        linebreak_size = 0
        for i,text in enumerate(texts):
            line = text[0]
            lineheight = text[1]
            if i > 0:
                linebreak_size += 20
                if lineheight == 20:
                    linebreak_size += 40
        
            color = [1.0,1.0,1.0,1.0]
            if lineheight == 20:
                color = headline_color
            self.write_text(line,size=lineheight,pos_y=linebreak_size,color=color)
        
        
        # restore opengl defaults
        bgl.glLineWidth(1)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
        