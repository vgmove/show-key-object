# Step Tools
# Copyright (C) 2025 VGmove
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
	"name" : "Step Tools",
	"description" : "Using animated material parameters to focus the main object",
	"author" : "VGmove",
	"version" : (1, 0, 0),
	"blender" : (4, 1, 0),
	"location" : "Dope Sheet > Edit > Step Tools",
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
class StepTools_properties(PropertyGroup):
	step_type: EnumProperty(
		name="",
		items=[('color', 'Color', 'Select blink options'),
			   ('transparent', 'Transparent', 'Select blink options')]
	)

	# Property for blink
	blend_blink: FloatProperty(
		name="Blend:",
		description="Blend of blink",
		default = 0.9,
		min = 0.5,
		max = 1
	)
	duration_blink: IntProperty(
		name="Duration:",
		description="Step length in frames",
		default = 12,
		min = 2,
		max = 100
	)
	count_blink: IntProperty(
		name="Count:",
		description="Number of blinks",
		default = 2,
		min = 1,
		max = 100
	)
	color_blink: FloatVectorProperty(
		name="Color",
		description="Color object blinks",
		subtype = "COLOR",
		default = (1.0,0.0,0.0,1.0),
		size = 4,
		min = 0, 
		max = 1
	)

	# Property for transparent
	transparent_type: EnumProperty(
		name="Action:",
		items= (
			("blink", "Blink", "Set keyframes for show an object"),
			("fade_in", "Fade In", "Set keyframes for show an object"),
			("fade_out", "Fade Out", "Set keyframes for hide an object"),
			("fade_inout", "Fade In/Out", "Set keyframes for Fade In/Out")
		),
		default = "blink"
	)
	blend_transparent: FloatProperty(
		name="Blend:",
		description="Blend of transparent",
		default = 1.0,
		min = 0.5,
		max = 1
	)
	duration_fade: IntProperty(
		name="Duration:",
		description="Step length in frames",
		default = 12,
		min = 3,
		max = 100
	)
	count_transparent_blink: IntProperty(
		name="Count:",
		description="Number of transparent",
		default = 2,
		min = 1,
		max = 100
	)
	delay_length: IntProperty(
		name="Delay length:",
		description="Multiplier for the delay length between appearance and disappearance",
		default = 2,
		min = 2,
		max = 10
	)

	# Property for pause
	duration_pause: IntProperty(
		name="Duration:",
		description="Length pause in frames",
		default = 24,
		min = 5,
		max = 50
	)

	# Property for settings
	move_cursor: BoolProperty(
		name="Move Cursor",
		description="Move timeline cursor to end new keyframe",
		default = True
	)
	set_marker: BoolProperty(
		name="Auto Set Marker",
		description="Auto set marker in keyframe before action",
		default = False
	)
	single_user_material: BoolProperty(
		name="Material",
		description="Make single user for materials",
		default = True
	)
	single_user_data: BoolProperty(
		name="Data",
		description="Make single user for data object",
		default = False
	)

# Blink
class StepToolsMain(Operator):
	bl_idname = "action.steptools_main"
	bl_label = "Step Tool Main"
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

			# Check OUTPUT_MATERIAL
			material_output = [node for node in material_nodes if node.type == "OUTPUT_MATERIAL"]
			if not material_output:
				material_output = material_nodes.new("ShaderNodeOutputMaterial")

			# Check available group
			groups = [node for node in material_nodes if node.type == "GROUP"]
			steptools_group = [group for group in groups if "StepTools" in group.node_tree.name]
			if not steptools_group:
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
		group = bpy.data.node_groups.new("StepTools", "ShaderNodeTree")
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
		attr_blink.attribute_name = '["StepTools_Blink"]'
		
		attr_blink_color = group.nodes.new(type='ShaderNodeAttribute')
		attr_blink_color.location = (0, -130)
		attr_blink_color.attribute_type = 'OBJECT'
		attr_blink_color.attribute_name = '["StepTools_Blink_Color"]'
		
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
		attr_transparent.attribute_name = '["StepTools_Transparent"]'
		
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
	
	# Property for custome object property
	def create_parameters(self, object):
		object["StepTools_Blink"] = 0.0
		object.id_properties_ui("StepTools_Blink").update(
			min=0.0,
			max=1.0,
			default=0.0,
			step=0.1,
			subtype='FACTOR'
		)

		object["StepTools_Blink_Color"] = [1.0, 0.0, 0.0]
		object.id_properties_ui("StepTools_Blink_Color").update(
			min=0.0,
			max=1.0,
			default=(1.0, 0.0, 0.0),
			step=0.1,
			subtype='COLOR'
		)

		object["StepTools_Transparent"] = 0.0
		object.id_properties_ui("StepTools_Transparent").update(
			min=0.0,
			max=1.0,
			default=0.0,
			step=0.1,
			subtype='FACTOR'
		)
		return {"FINISHED"}

class StepToolsBlink(StepToolsMain):
	bl_idname = "action.steptools_blink"
	bl_label = "Set Keyframes Blink"
	bl_description = "Set keyframes for blink"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		StepToolsMain.execute(self, context)

		self.curent_frame = bpy.context.scene.frame_current
		for object in self.objects:
			object["StepTools_Blink"] = 0.0
			object["StepTools_Blink_Color"] = context.scene.property.color_blink
			
			for i in range(context.scene.property.count_blink * 2 + 1):
				value = 0.0 if i % 2 == 0 else context.scene.property.blend_blink
				frame = bpy.context.scene.frame_current + i * context.scene.property.duration_blink
				self.curent_frame = frame
				object["StepTools_Blink"] = value
				object.update_tag()
				object.keyframe_insert(data_path='["StepTools_Blink"]', frame = frame)
				
				# Set keyframes for color
				if i == 0 or i == context.scene.property.count_blink * 2:
					object["StepTools_Blink_Color"] = context.scene.property.color_blink
					object.update_tag()
					object.keyframe_insert(data_path='["StepTools_Blink_Color"]', frame=frame)
		StepToolsCursor.execute(self, context)
		return {"FINISHED"}

class StepToolsTransparent(StepToolsMain):
	bl_idname = "action.steptools_transparent"
	bl_label = "Set Keyframes Transparent"
	bl_description = "Set keyframes for transparency"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		StepToolsMain.execute(self, context)
		self.curent_frame = bpy.context.scene.frame_current
		for object in self.objects:
			if context.scene.property.transparent_type == "blink":
				count_transparent_blink = context.scene.property.count_transparent_blink * 2 + 1
				range_data = (count_transparent_blink, 0.0, context.scene.property.blend_transparent)
			elif context.scene.property.transparent_type == "fade_in":
				range_data = (2, context.scene.property.blend_transparent, 0.0)
			elif context.scene.property.transparent_type == "fade_out":
				range_data = (2, 0.0, context.scene.property.blend_transparent)
			elif context.scene.property.transparent_type == "fade_inout":
				range_data = (4, context.scene.property.blend_transparent, 0.0)

			for i in range(range_data[0]):
				value = range_data[1] if i % 2 == 0 else range_data[2]
				frame = bpy.context.scene.frame_current + i * context.scene.property.duration_fade
				self.curent_frame = frame
				
				# Set keyframes for transparency
				if context.scene.property.transparent_type == "fade_inout":
					if i == 2:
						frame += context.scene.property.duration_fade * context.scene.property.delay_length
					elif i == 3:
						frame += context.scene.property.duration_fade * (context.scene.property.delay_length - 2)
						self.curent_frame = frame + context.scene.property.duration_fade

				object["StepTools_Transparent"] = value
				object.update_tag()
				object.keyframe_insert(data_path='["StepTools_Transparent"]', frame = frame)
		StepToolsCursor.execute(self, context)
		return {"FINISHED"}

class StepToolsCursor(Operator):
	bl_idname = "action.steptools_cursor"
	bl_label = "Move Cursor"
	bl_options = {"REGISTER", "UNDO"}
	
	def execute(self, context):
		if self.objects and context.scene.property.move_cursor:
			context.scene.frame_set(self.curent_frame)
			if context.scene.property.set_marker:
				StepToolsMarker.execute(self, context)
		return {'FINISHED'}

class StepToolsFadeIn(StepToolsTransparent):
	bl_idname = "action.steptools_fade_in"
	bl_label = "Fade In"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.transparent_type = "fade_in"
		StepToolsTransparent.execute(self, context)
		return {'FINISHED'}

class StepToolsFadeOut(StepToolsTransparent):
	bl_idname = "action.steptools_fade_out"
	bl_label = "Fade Out"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.transparent_type = "fade_out"
		StepToolsTransparent.execute(self, context)
		return {'FINISHED'}

class StepToolsFadeInOut(StepToolsTransparent):
	bl_idname = "action.steptools_fade_inout"
	bl_label = "Fade In/Out"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		context.scene.property.transparent_type = "fade_inout"
		StepToolsTransparent.execute(self, context)
		return {'FINISHED'}

# Pause
class StepToolsMarker(Operator):
	bl_idname = "action.steptools_marker"
	bl_label = "Set Marker"
	bl_description = "Set marker for pause"
	bl_options = {"REGISTER", "UNDO"}

	def execute(self, context):
		curent_frame = bpy.context.scene.frame_current
		context.scene.timeline_markers.new('P', frame=curent_frame)
		return {'FINISHED'}

class StepToolsMarkerSave(Operator):
	bl_idname = "action.steptools_marker_save"
	bl_label = "Save Markers"
	bl_description = "Save markers with name 'P' to .txt file"
	
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

class StepToolsPause(Operator):
	bl_idname = "action.steptools_pause"
	bl_label = "Create Pause"
	bl_description = "Select pauses file and create pause on selected sequence"
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
			marker_offset = marker + start_frame + step # '-set 'start_frame' if start not 0 frame   		
			if marker_offset in range(end_strip.frame_final_start, end_strip.frame_final_end + 1):
				next_strip = end_strip.split(marker_offset, "SOFT")
				if next_strip is None:
					next_strip = end_strip

				# Next strip
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

# Draw UI in DopeSheet
class StepToolsDopeSheet:
	bl_space_type = "DOPESHEET_EDITOR"
	bl_region_type = "UI"
	bl_category = "Action"
	bl_options = {"DEFAULT_CLOSED"}

class STEPTOOLS_PT_dopesheet_panel(StepToolsDopeSheet, Panel):
	bl_idname = "STEPTOOLS_PT_dopesheet_panel"
	bl_label = "Step Tools"

	@classmethod
	def poll(self,context):
		return context.active_object is not None

	def draw(self, context):
		layout = self.layout

class STEPTOOLS_PT_subpanel_blink(StepToolsDopeSheet, Panel):
	bl_parent_id = "STEPTOOLS_PT_dopesheet_panel"
	bl_label = "Blink"

	def draw(self, context):
		layout = self.layout
		layout.prop(context.scene.property, "step_type")
		
		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		if context.scene.property.step_type == 'color':
			steptools_action = StepToolsBlink.bl_idname

			col.prop(context.scene.property, "color_blink")
			col.prop(context.scene.property, "blend_blink")
			col.prop(context.scene.property, "duration_blink")
			col.prop(context.scene.property, "count_blink")

		elif context.scene.property.step_type == 'transparent':
			steptools_action = StepToolsTransparent.bl_idname

			col.prop(context.scene.property, "transparent_type")
			col.prop(context.scene.property, "blend_transparent")
			col.prop(context.scene.property, "duration_fade")

			if context.scene.property.transparent_type == "blink":
				col.prop(context.scene.property, "count_transparent_blink")
			
			if context.scene.property.transparent_type == "fade_inout":
				col.prop(context.scene.property, "delay_length")

		col.separator()
		row = col.row()
		row.operator(steptools_action, text="Set Keyframes", icon="KEYFRAME_HLT")
		row.scale_x = 1
		row.operator(StepToolsMarker.bl_idname, text="", icon="MARKER_HLT")

class STEPTOOLS_PT_subpanel_settings(StepToolsDopeSheet, Panel):
	bl_parent_id = "STEPTOOLS_PT_dopesheet_panel"
	bl_label = "Settings"

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		col.prop(context.scene.property, "move_cursor")

		row = col.row()
		row.prop(context.scene.property, "set_marker")
		if not context.scene.property.move_cursor:
			row.enabled = False

		row = col.row()
		split = row.split(factor=0.4)
		split.alignment = 'RIGHT'
		split.label(text="Single User:")
		col_right = split.column()
		col_right.use_property_split = False
		col_right.prop(context.scene.property, "single_user_material")
		col_right.prop(context.scene.property, "single_user_data")

		split = col.split(factor=0.4)
		split.alignment = 'RIGHT'
		split.label(text="Save Marker:")
		split.operator(StepToolsMarkerSave.bl_idname, icon="FILE_TICK", text="")

# Draw UI in Sequencer
class StepToolsSequencer:
	bl_space_type = "SEQUENCE_EDITOR"
	bl_region_type = "UI"
	bl_category = "Strip"
	bl_options = {"DEFAULT_CLOSED"}

class STEPTOOLS_PT_sequencer_panel(StepToolsSequencer, Panel):
	bl_idname = "STEPTOOLS_PT_sequencer_panel"
	bl_label = "Pause"
	
	@classmethod
	def poll(cls, context):
		return bpy.context.scene.sequence_editor.active_strip is not None

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.use_property_split = True
		col.use_property_decorate = False

		col.prop(context.scene.property, "duration_pause")
		col.operator(StepToolsPause.bl_idname, icon="CENTER_ONLY", text="Create Pause")

# Draw UI Context Menu
class STEPTOOLS_MT_menu(Menu):
	bl_idname = "STEPTOOLS_MT_menu"
	bl_label = "Step Tools"

	def draw(self, context):
		layout = self.layout
		layout.separator()
		layout.menu(STEPTOOLS_MT_submenu.bl_idname)

class STEPTOOLS_MT_submenu(Menu):
	bl_idname = "STEPTOOLS_MT_submenu"
	bl_label = "Step Tools"

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def draw(self, context):
		layout = self.layout
		layout.operator(StepToolsBlink.bl_idname)
		layout.operator(StepToolsTransparent.bl_idname)
		layout.separator()
		layout.operator(StepToolsMarker.bl_idname)

classes = (
	StepTools_properties,
	StepToolsMain,
	StepToolsBlink,
	StepToolsFadeIn,
	StepToolsFadeOut,
	StepToolsFadeInOut,
	StepToolsTransparent,
	StepToolsCursor,
	StepToolsMarkerSave,
	StepToolsMarker,
	StepToolsPause,
	STEPTOOLS_PT_dopesheet_panel,
	STEPTOOLS_PT_subpanel_blink,
	STEPTOOLS_PT_subpanel_settings,
	STEPTOOLS_MT_menu,
	STEPTOOLS_MT_submenu,
	STEPTOOLS_PT_sequencer_panel
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.property = PointerProperty(type = StepTools_properties)
	bpy.types.DOPESHEET_MT_key.append(STEPTOOLS_MT_menu.draw)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	
	del bpy.types.Scene.property
	bpy.types.DOPESHEET_MT_key.remove(STEPTOOLS_MT_menu.draw)

if __name__ == "__main__" :
	register()