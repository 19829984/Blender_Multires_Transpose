import bpy
import bmesh
import time
import logging
from .utils.bmesh_context import bmesh_from_obj
from .utils.utils import copy_multires_objs_to_new_mesh, split_meshes_by_original_name, restore_vertex_index
import numpy as np


class LoggerOperator(bpy.types.Operator):
    def __init__(self):
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)


class MULTIRES_TRANSPOSE_OT_create_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.create_transpose_target"
    bl_label = "Create Transpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    multires_level: bpy.props.IntProperty(name="Multires Level", default=1, min=1)
    use_multires_level_as_is: bpy.props.BoolProperty(name="Use Multires Level As Is", default=False)

    def execute(self, context):
        start_time = time.time()

        transpose_target = copy_multires_objs_to_new_mesh(context, context.selected_objects, self.multires_level)
        transpose_target.name = "Multires_Transpose_Target"

        for obj in context.selected_objects:
            obj.select_set(False)
        context.view_layer.objects.active = transpose_target
        transpose_target.select_set(True)

        self.logger.info(f"Time taken to create Transpose Target: {time.time() - start_time}")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Settings:", icon="SETTINGS")
        row = col.row()
        row.scale_y = 1.2
        row.alignment = 'CENTER'
        row.prop(self, "use_multires_level_as_is", text="Use Multires Level As Is")

        row = col.row()
        row.prop(self, "multires_level", text="Multires Level To Use")
        row.enabled = not self.use_multires_level_as_is

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class MULTIRES_TRANSPOSE_OT_apply_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.apply_transpose_target"
    bl_label = "Apply Transpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(name="Threshold", default=0.01, min=0.0, step=0.01)
    auto_iterations: bpy.props.BoolProperty(name="Auto Iterations", default=False)
    max_auto_iterations: bpy.props.IntProperty(name="Max Auto Iterations", default=50, min=1)
    max_iterations: bpy.props.IntProperty(name="Max Iterations", default=5, min=1)

    def execute(self, context):
        start_time = time.time()

        active_obj = context.active_object
        if active_obj.name != "Multires_Transpose_Target":
            self.report({'WARNING'}, "Selected object does not have name 'Multires_Transpose_Target', operation may fail")

        transpose_targets = split_meshes_by_original_name(active_obj)
        for object in transpose_targets:
            original_obj_name = ""
            with bmesh_from_obj(object) as bm:
                original_obj_name = object.name[:-len("_Target")]
            if original_obj_name not in bpy.data.objects:
                self.logger.warn(f"Object {object.name} does not have original object name recorded, skipping")
                continue

            original_obj = bpy.data.objects[original_obj_name]
            with bmesh_from_obj(object) as bm:
                restore_vertex_index(bm)
                bmesh.ops.transform(bm, verts=bm.verts, matrix=original_obj.matrix_world.inverted())

                diff = self.threshold + 1
                last_diff = 0
                iteration = 0

                bm.to_mesh(object.data)
                selected_objs = (original_obj, object)

                with bpy.context.temp_override(object=original_obj, selected_editable_objects=selected_objs):
                    if not self.auto_iterations:
                        for _ in range(self.max_iterations):
                            bpy.ops.object.multires_reshape(modifier="Multires")
                    else:
                        while diff > self.threshold and (abs(diff - last_diff) > 0.00001) and iteration < self.max_auto_iterations:
                            bpy.ops.object.multires_reshape(modifier="Multires")

                            # Calculate diff
                            depsgraph = context.evaluated_depsgraph_get()
                            multires_mesh = depsgraph.objects[original_obj.name].data
                            verts = np.array([v.co for v in multires_mesh.vertices])
                            new_verts = np.array([v.co for v in bm.verts])
                            last_diff = diff
                            diff = np.abs(verts - new_verts).max()

                            iteration += 1

                bmesh.ops.transform(bm, verts=bm.verts, matrix=original_obj.matrix_world)

        # Remove all transpose targets
        for obj in transpose_targets:
            bpy.data.objects.remove(obj)

        self.logger.info(f"Time taken to apply Transpose Target: {time.time() - start_time}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Settings:", icon="SETTINGS")

        row = col.row()
        row.prop(self, "auto_iterations", text="Auto Iterations")
        if self.auto_iterations:
            row = col.row()
            row.prop(self, "threshold", text="Difference Threshold")
            row.prop(self, "max_auto_iterations", text="Max Auto Iterations")
        else:
            row = col.row()
            row.prop(self, "max_iterations", text="Max Iterations")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, MULTIRES_TRANSPOSE_OT_apply_transpose_target)

register, unregister = bpy.utils.register_classes_factory(classes)
