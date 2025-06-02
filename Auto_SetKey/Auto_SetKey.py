# Auto SetKey
# Copyright (C) 2024 VGmove
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
	"name" : "Auto SetKey",
	"description" : "Automatically set keys for repeating types of actions",
	"author" : "VGmove",
	"version" : (1, 0, 0),
	"blender" : (4, 1, 00),
	"location" : "Dope Sheet > Edit > SetKey",
	"category" : "Animation"
}

import os
import bpy
from collections import Counter
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )
from bpy.types import (Menu,
                       Panel,
                       Operator,
                       PropertyGroup,
                       )

# Scene Properties
class SETKEY_Properties(PropertyGroup):
	blend_blink : FloatProperty(
		name="Blend:",
		description="Blend of blinks",
		default = 0.9,
		min = 0.5,
		max = 1
	)
	duration_blink : IntProperty(
		name="Duration:",
		description="Step length in frames",
		default = 12,
		min = 2,
		max = 100
	)
	count_blink : IntProperty(
		name="Count:",
		description="Number of blinks",
		default = 2,
		min = 1,
		max = 100
	)
	color_blink : FloatVectorProperty(
		name="Color",
		description="Color object blinks",
		subtype = "COLOR",
		default = (1.0,0.0,0.0,1.0),
		size = 4,
		min = 0, 
		max = 1
	)
	duration_fade : IntProperty(
		name="Duration:",
		description="Step length in frames",
		default = 12,
		min = 3,
		max = 100
	)
	length_step : IntProperty(
		name="Length Step:",
		description="Length of the step between appearance and disappearance",
		default = 2,
		min = 2,
		max = 10
	)										
	toggle_type : EnumProperty(
		items= (
			("1", "Show", "Set keys for show an object"),
			("2", "In/Out", "FadeIn / FadeOut"),
			("3", "Hide", "Set keys for hide an object")
		),
		default = "2"
	)
	duration_pause : IntProperty(
		name="Duration:",
		description="Step length in frames",
		default = 24,
		min = 5,
		max = 50
	)
	move_cursor : BoolProperty(
		name="Move Timeline Cursor",
		description="Move Timeline Cursor to end new keyframe",
		default = True
	)
	set_marker_pause : BoolProperty(
		name="Auto Set Pause",
		description="Auto set marker pause in keyframe before action",
		default = False
	)
	single_user_material : BoolProperty(
		name="Single User Material",
		description="Make single user for materials",
		default = True
	)
	single_user_data : BoolProperty(
		name="Single User Data",
		description="Make single user for data object",
		default = False
	)

# Blink
class SETKEY_Main(Operator):
	bl_idname = "action.setkey_main"
	bl_label = "Set Key Main"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		selected_objects = [obj for obj in bpy.context.selected_objects if obj.data is not None]

		# Get all materials
		all_materials = []
		for obj in selected_objects:
			for mat in obj.material_slots:
				all_materials.append(mat.name)

		materials = []
		self.objects = []
		for object in selected_objects:
			# Create single user object (if needed)
			if context.scene.property.single_user_data and object.data.users > 1:
				object.data = object.data.copy()
			
			for id, slot in enumerate(object.material_slots):
				material = object.material_slots[id].material
				if not material or not material and not material.use_nodes:
					continue
				else:
					# Create single user material (if needed)
					if context.scene.property.single_user_material and material.users > 1:
						if material.users != all_materials.count(material.name):
							material = material.copy()
							if material.node_tree.animation_data and material.node_tree.animation_data.action:
								material.node_tree.animation_data.action = material.node_tree.animation_data.action.copy()
							object.material_slots[id].material = material

					# Add material to list
					if not material in materials:
						materials.append(material)
						
					# Add object to list	
					if not object in self.objects:
						self.objects.append(object)
		
		# Check materials group 
		for material in materials:
			material_nodes = material.node_tree.nodes
			links = material.node_tree.links
			
			# Material parameters
			material.use_raytrace_refraction = True

			# Check OUTPUT_MATERIAL
			material_output = [node for node in material_nodes if node.type == "OUTPUT_MATERIAL"]
			if not material_output:
				material_output = material_nodes.new("ShaderNodeOutputMaterial")

			# Check available group
			groups = [node for node in material_nodes if node.type == "GROUP"]
			auto_setkey_group = [group for group in groups if "Auto_SetKey" in group.node_tree.name]
			if not auto_setkey_group:
				self.create_group(context, material_output[0], material_nodes, links)
		
		
		for object in self.objects:
			# Create custom properties
			self.create_parameters(object)
		
			# Remove empty action and data
			if object.animation_data and not object.animation_data.action:
				object.animation_data.action = None
				object.animation_data_clear()

		# Remove empty actions
		for action in bpy.data.actions:
			if action.users == 0:
				bpy.data.actions.remove(action)
		return {"FINISHED"}

	def create_group(self, context, material_output, material_nodes, links):
		# Create input \ output nodes
		group = bpy.data.node_groups.new("Auto_SetKey", "ShaderNodeTree")
		group_input : bpy.types.ShaderNodeGroup = group.nodes.new("NodeGroupInput")
		group_input.location = (0, 5)
		group_output : bpy.types.ShaderNodeGroup = group.nodes.new("NodeGroupOutput")
		group_output.location = (1200, 0)
		
		group.interface.new_socket(name="Shader", description="Shader Input", in_out ="INPUT", socket_type="NodeSocketShader")
		group.interface.new_socket(name="Shader", description="Shader Output", in_out ="OUTPUT", socket_type="NodeSocketShader")
		
		# Nodes for blink
		mix_shader_blink = group.nodes.new("ShaderNodeMixShader")
		mix_shader_blink.location = (600,50)
		mix_shader_blink_inputs = [input for input in mix_shader_blink.inputs if input.name == "Shader"]
		
		emission_shader = group.nodes.new("ShaderNodeEmission")
		emission_shader.location = (300, -200)
		
		attr_blink = group.nodes.new(type='ShaderNodeAttribute')
		attr_blink.location = (300, 300)
		attr_blink.attribute_type = 'OBJECT'
		attr_blink.attribute_name = '["SetKey_Blink"]'
		
		attr_blink_color = group.nodes.new(type='ShaderNodeAttribute')
		attr_blink_color.location = (0, -130)
		attr_blink_color.attribute_type = 'OBJECT'
		attr_blink_color.attribute_name = '["SetKey_Blink_Color"]'
		
		# Nodes for transparency
		mix_shader_transparent = group.nodes.new("ShaderNodeMixShader")
		mix_shader_transparent.location = (900,50)
		mix_shader_transparent_inputs = [input for input in mix_shader_transparent.inputs if input.name == "Shader"]
		
		transparent_shader = group.nodes.new("ShaderNodeBsdfTransparent")
		transparent_shader.location = (600, -200)
		transparent_shader.inputs["Color"].default_value = (1, 1, 1, 0)
		
		attr_transparent = group.nodes.new(type='ShaderNodeAttribute')
		attr_transparent.location = (600, 300)
		attr_transparent.attribute_type = 'OBJECT'
		attr_transparent.attribute_name = '["SetKey_Transparent"]'
		
		# Create link
		group.links.new(group_input.outputs["Shader"], mix_shader_blink_inputs[0])
		group.links.new(attr_blink.outputs["Fac"], mix_shader_blink.inputs["Fac"])
		group.links.new(attr_blink_color.outputs["Color"], emission_shader.inputs["Color"])	
		group.links.new(emission_shader.outputs["Emission"], mix_shader_blink_inputs[1])
		
		group.links.new(mix_shader_blink.outputs["Shader"], mix_shader_transparent_inputs[0])
		group.links.new(attr_transparent.outputs["Fac"], mix_shader_transparent.inputs["Fac"])
		group.links.new(transparent_shader.outputs["BSDF"], mix_shader_transparent_inputs[1])
		group.links.new(mix_shader_transparent.outputs["Shader"], group_output.inputs["Shader"])
		
		# Create group node
		group_node = material_nodes.new("ShaderNodeGroup")
		group_node.node_tree = group
		group_node.location = material_output.location
		material_output.location.x = material_output.location.x + 250
		
		if material_output.inputs["Surface"].links:
			links.new(material_output.inputs["Surface"].links[0].from_node.outputs[0], group_node.inputs[0])
			links.new(group_node.outputs["Shader"], material_output.inputs["Surface"])
		else:
			links.new(group_node.outputs["Shader"], material_output.inputs["Surface"])
		return {"FINISHED"}
	
	def create_parameters(self, object):
		object["SetKey_Blink"] = 0.0
		object.id_properties_ui("SetKey_Blink").update(
			min=0.0,
			max=1.0,
			default=0.0,
			step=0.1,
			subtype='FACTOR'
		)

		object["SetKey_Blink_Color"] = [1.0, 0.0, 0.0]
		object.id_properties_ui("SetKey_Blink_Color").update(
			min=0.0,
			max=1.0,
			default=(1.0, 0.0, 0.0),
			step=0.1,
			subtype='COLOR'
		)

		object["SetKey_Transparent"] = 0.0
		object.id_properties_ui("SetKey_Transparent").update(
			min=0.0,
			max=1.0,
			default=0.0,
			step=0.1,
			subtype='FACTOR'
		)
		return {"FINISHED"}

class SETKEY_Blink(SETKEY_Main):
	bl_idname = "action.setkey_blink"
	bl_label = "Set Key Blink"
	bl_description = "Auto set key for blink"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		SETKEY_Main.execute(self, context)
		self.curent_frame = bpy.context.scene.frame_current
		for object in self.objects:
			object["SetKey_Blink"] = 0.0
			object["SetKey_Blink_Color"] = context.scene.property.color_blink
			
			for i in range(context.scene.property.count_blink * 2 + 1):
				value = 0.0 if i % 2 == 0 else context.scene.property.blend_blink
				frame = bpy.context.scene.frame_current + i * context.scene.property.duration_blink
				self.curent_frame = frame
				object["SetKey_Blink"] = value
				object.keyframe_insert(data_path='["SetKey_Blink"]', frame = frame)
				
				# Set key frame for color
				if i == 0 or i == context.scene.property.count_blink * 2:
					object.keyframe_insert(data_path='["SetKey_Blink_Color"]', index = 0, frame = frame)
					object.keyframe_insert(data_path='["SetKey_Blink_Color"]', index = 1, frame = frame)
					object.keyframe_insert(data_path='["SetKey_Blink_Color"]', index = 2, frame = frame)
		SETKEY_Cursor.execute(self, context)
		return {"FINISHED"}

class SETKEY_Transparent(SETKEY_Main):
	bl_idname = "action.setkey_transparent"
	bl_label = "Set Key Transparent"
	bl_description = "Auto set key for transparency"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		SETKEY_Main.execute(self, context)
		self.curent_frame = bpy.context.scene.frame_current
		for object in self.objects:
			if context.scene.property.toggle_type == "1":
				range_data = (2, 1.0, 0.0)
			elif context.scene.property.toggle_type == "2":
				range_data = (4, 1.0, 0.0)
			elif context.scene.property.toggle_type == "3":
				range_data = (2, 0.0, 1.0)

			for i in range(range_data[0]):
				value = range_data[1] if i % 2 == 0 else range_data[2]
				frame = bpy.context.scene.frame_current + i * context.scene.property.duration_fade
				self.curent_frame = frame
				
				if context.scene.property.toggle_type == "2":
					if i == 2:
						frame += context.scene.property.duration_fade * context.scene.property.length_step
					elif i == 3:
						frame += context.scene.property.duration_fade * (context.scene.property.length_step - 2)
						self.curent_frame = frame + context.scene.property.duration_fade

				object["SetKey_Transparent"] = value
				object.keyframe_insert(data_path='["SetKey_Transparent"]', frame = frame)
		SETKEY_Cursor.execute(self, context)
		return {"FINISHED"}

class SETKEY_Cursor(Operator):
	bl_idname = "action.cursor"
	bl_label = "Set Key Cursor"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		if self.objects:
			# Set frame cursor in timeline
			if context.scene.property.move_cursor:
				context.scene.frame_set(self.curent_frame)
				# Auto set marker pause 
				if context.scene.property.set_marker_pause:
					SETKEY_Marker.execute(self, context)
		return {'FINISHED'}

class SETKEY_Transparent_Show(SETKEY_Transparent):
	bl_idname = "action.setkey_transparent_show"
	bl_label = "Transparent Show"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.toggle_type = "1"
		SETKEY_Transparent.execute(self, context)
		return {'FINISHED'}

class SETKEY_Transparent_InOut(SETKEY_Transparent):
	bl_idname = "action.setkey_transparent_inout"
	bl_label = "Transparent In/Out"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.toggle_type = "2"
		SETKEY_Transparent.execute(self, context)
		return {'FINISHED'}

class SETKEY_Transparent_Hide(SETKEY_Transparent):
	bl_idname = "action.setkey_transparent_hide"
	bl_label = "Transparent Hide"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.toggle_type = "3"
		SETKEY_Transparent.execute(self, context)
		return {'FINISHED'}

# Pause
class SETKEY_Marker(Operator):
	bl_idname = "action.setkey_marker"
	bl_label = "Set Marker Pause"
	bl_description = "Set marker for pause"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		curent_frame = bpy.context.scene.frame_current
		context.scene.timeline_markers.new('P', frame=curent_frame)
		return {'FINISHED'}

class SETKEY_Marker_Save(Operator):
	bl_idname = "action.setkey_marker_save"
	bl_label = "Save Marker"
	
	filepath: StringProperty(subtype="FILE_PATH")

	def execute(self, context):
		directory = os.path.dirname(self.filepath)
		if not os.path.exists(directory):
			self.report({'ERROR'}, "Директория не существует")
			return {'CANCELLED'}
		
		# Get markers
		markers = []
		for marker in bpy.context.scene.timeline_markers:
			if marker.name == "P" and marker.frame not in markers:
				markers.extend([marker.frame])
		markers = sorted(markers)

		# Save markers
		with open(self.filepath + '.txt', 'w', encoding='utf-8') as f:
			for marker in markers:
				f.write(f"{marker} ")
			self.report({'INFO'}, 'Markers saved.')
		return {'FINISHED'}

	def invoke(self, context, event):
		self.filepath = bpy.context.scene.render.filepath
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}

class SETKEY_Pause(Operator):
	bl_idname = "action.setkey_pause"
	bl_label = "Create Pause"
	bl_description = "Create pause on selected sequence"
	bl_options = {"REGISTER", "UNDO"}
	
	filepath: StringProperty(subtype="FILE_PATH")
	filter_glob: StringProperty(
		default="*.txt",
		options={'HIDDEN'},
		maxlen=255
	)

	def execute(self, context):
		active_strip = bpy.context.scene.sequence_editor.active_strip
		if len(bpy.context.selected_sequences) == 1 and active_strip.type == "IMAGE":
			markers = self.get_markers(context, self.filepath)
			if markers:
				active_strip_path = bpy.path.abspath(active_strip.directory)
				self.create_pause(context, markers, active_strip, active_strip_path)
		return {'FINISHED'}
	
	def get_markers(self, context, active_strip_path):
		markers = []
		with open(active_strip_path) as f:
			for marker in f.readline().split():
				if marker.isdigit():
					markers.append(int(marker))
		return markers

	def create_pause(self, context, markers, active_strip, active_strip_path):
		step = 0
		start_frame = active_strip.frame_final_start
		active_strip_length = active_strip.frame_final_end
		duration_pause = context.scene.property.duration_pause
		for marker in markers:
			end_strip = bpy.context.selected_sequences[-1]
			marker_offset = marker + start_frame + step # '-set_start_frame' if start not 0 frame			
			if marker_offset in range(end_strip.frame_final_start, end_strip.frame_final_end + 1):
				next_strip = end_strip.split(marker_offset, "SOFT")
				if next_strip is None:
					next_strip = end_strip

				# Set next strip
				next_strip.frame_start += duration_pause
				if marker == markers[-1] and marker_offset == end_strip.frame_final_end - duration_pause:
					next_strip.frame_start -= duration_pause

				# Add images to sequence
				sequence_image = next_strip.strip_elem_from_frame(marker_offset + duration_pause).filename
				image = active_strip_path + sequence_image
				sequences = bpy.context.scene.sequence_editor.sequences
				image_strip = sequences.new_image("Image", image, active_strip.channel, marker_offset)
				image_strip.select = False
				image_strip.frame_final_duration = duration_pause
				image_strip.color_tag = "COLOR_05"
				
				step += context.scene.property.duration_pause
		bpy.context.scene.frame_end = active_strip_length + step - 1
		bpy.context.scene.frame_start = start_frame
		return {"FINISHED"}
	
	def invoke(self, context, event):
		active_strip = bpy.context.scene.sequence_editor.active_strip
		if len(bpy.context.selected_sequences) == 1 and active_strip.type == "IMAGE":
			self.filepath = bpy.path.abspath(active_strip.directory)
		else:
			self.filepath = bpy.context.scene.render.filepath
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}

# Draw UI in TimeLine
class SETKEY_panel:
	bl_space_type = "DOPESHEET_EDITOR"
	bl_region_type = "UI"
	bl_category = "Action"
	bl_options = {"DEFAULT_CLOSED"}

class SETKEY_PT_panel(SETKEY_panel, Panel):
	bl_idname = "SETKEY_PT_panel"
	bl_label = "Auto SetKey"

	@classmethod
	def poll(self,context):
		return context.active_object is not None

	def draw(self, context):
		layout = self.layout

class SETKEY_PT_subpanel_1(SETKEY_panel, Panel):
	bl_parent_id = "SETKEY_PT_panel"
	bl_label = "Blink"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		row = col.row()
		row.prop(context.scene.property, "color_blink")
		col = layout.column(align=True)
		col.prop(context.scene.property, "blend_blink")
		col.prop(context.scene.property, "duration_blink")
		col.prop(context.scene.property, "count_blink")
		col.separator()
		row = col.row()
		row.label(text="Set Keys:")
		row.scale_x = 15
		row.operator(SETKEY_Blink.bl_idname, text="", icon="KEYFRAME_HLT")

class SETKEY_PT_subpanel_2(SETKEY_panel, Panel):
	bl_parent_id = "SETKEY_PT_panel"
	bl_label = "Transparent"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col = layout.column(align=True)
		
		row = col.row()
		row.alignment = "RIGHT"
		row.prop(context.scene.property, "toggle_type", expand=True)
		row = col.row()
		row.prop(context.scene.property, "duration_fade")
		
		row = col.row()
		row.prop(context.scene.property, "length_step")
		if not context.scene.property.toggle_type == "2":
			row.enabled = False
		
		col.separator()
		row = col.row()
		row.label(text="Set Keys:")
		row.scale_x = 15
		row.operator(SETKEY_Transparent.bl_idname, text="", icon="KEYFRAME_HLT")

class SETKEY_PT_subpanel_3(SETKEY_panel, Panel):
	bl_parent_id = "SETKEY_PT_panel"
	bl_label = "Pause"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		row = col.row()
		row = col.row(align=True)
		row.operator(SETKEY_Marker_Save.bl_idname, text="Save", icon="FILE")
		col.separator()
		row = col.row()
		row.label(text="Set Marker:")
		row.scale_x = 15
		row.operator(SETKEY_Marker.bl_idname, text="", icon="MARKER_HLT")

class SETKEY_PT_subpanel_4(SETKEY_panel, Panel):
	bl_parent_id = "SETKEY_PT_panel"
	bl_label = "Settings"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.alignment = "LEFT"
		col.prop(context.scene.property, "move_cursor")
		
		row = col.row()
		row.prop(context.scene.property, "set_marker_pause")
		if not context.scene.property.move_cursor:
			row.enabled = False

		col.prop(context.scene.property, "single_user_material")
		col.prop(context.scene.property, "single_user_data")

# Draw UI in Sequencer
class SETKEY_panel_se:
	bl_space_type = "SEQUENCE_EDITOR"
	bl_region_type = "UI"
	bl_category = "Tool"
	bl_options = {"DEFAULT_CLOSED"}

class SETKEY_PT_panel_se(SETKEY_panel_se, Panel):
	bl_idname = "SETKEY_PT_panel_se"
	bl_label = "Auto SetKey"
	
	@classmethod
	def poll(cls, context):
		return bpy.context.scene.sequence_editor.active_strip is not None

	def draw(self, context):
		layout = self.layout

class SETKEY_PT_subpanel_se_1(SETKEY_panel_se, Panel):
	bl_parent_id = "SETKEY_PT_panel_se"
	bl_label = "Pause"

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)
		col.prop(context.scene.property, "duration_pause")
		row = col.row()
		row = col.row(align=True)
		row.operator(SETKEY_Pause.bl_idname, text="Load", icon="CENTER_ONLY")

# Draw UI Context Menu
class SETKEY_MT_menu(Menu):
	bl_idname = "SETKEY_MT_menu"
	bl_label = "Auto SetKey"

	def draw(self, context):
		layout = self.layout
		layout.separator()
		layout.menu(SETKEY_MT_submenu.bl_idname)

class SETKEY_MT_submenu(Menu):
	bl_idname = "SETKEY_MT_submenu"
	bl_label = "Auto SetKey"

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def draw(self, context):
		layout = self.layout
		layout.operator(SETKEY_Blink.bl_idname, icon="KEYFRAME_HLT")
		layout.separator()
		layout.operator(SETKEY_Transparent_Show.bl_idname, icon="HIDE_OFF")
		layout.operator(SETKEY_Transparent_InOut.bl_idname, icon="SMOOTHCURVE")
		layout.operator(SETKEY_Transparent_Hide.bl_idname, icon="HIDE_ON")
		layout.separator()
		layout.operator(SETKEY_Marker.bl_idname, icon="MARKER_HLT")

classes = (
	SETKEY_Properties,
	SETKEY_Main,
	SETKEY_Blink,
	SETKEY_Transparent_Show,
	SETKEY_Transparent_InOut,
	SETKEY_Transparent_Hide,
	SETKEY_Transparent,
	SETKEY_Cursor,
	SETKEY_Marker_Save,
	SETKEY_Marker,
	SETKEY_Pause,
	SETKEY_PT_panel,
	SETKEY_PT_subpanel_1,
	SETKEY_PT_subpanel_2,
	SETKEY_PT_subpanel_3,
	SETKEY_PT_subpanel_4,
	SETKEY_MT_menu,
	SETKEY_MT_submenu,
	SETKEY_PT_panel_se,
	SETKEY_PT_subpanel_se_1
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.property = PointerProperty(type = SETKEY_Properties)
	bpy.types.DOPESHEET_MT_context_menu.append(SETKEY_MT_menu.draw)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	
	del bpy.types.Scene.property
	bpy.types.DOPESHEET_MT_context_menu.remove(SETKEY_MT_menu.draw)

if __name__ == "__main__" :
	register()