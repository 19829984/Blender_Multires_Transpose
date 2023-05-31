import bpy
import bmesh
import time
import logging
from .data_types import MeshDomain, MeshLayerType
from .utils.bmesh_context import bmesh_from_obj
from .utils.utils import copy_multires_objs_to_new_mesh, create_meshes_by_original_name, restore_vertex_index
from .utils.utils import ORIGINAL_SUBDIVISION_LEVEL_LAYER
from .utils.bmesh_utils import bmesh_copy_vert_location, read_layer_data
import numpy as np

TRANSPOSE_TARGET_NAME = "Multires_Transpose_Target"


class LoggerOperator(bpy.types.Operator):
    def __init__(self):
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)


class MULTIRES_TRANSPOSE_OT_create_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.create_transpose_target"
    bl_label = "Create Transpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    multires_level: bpy.props.IntProperty(
        name="Multires Level",
        default=1,
        min=0,
        description="Multires subdivision level to use when creating the transpose target. Only used if 'Use Multires Level As Is' is disabled"
    )
    use_multires_level_as_is: bpy.props.BoolProperty(
        name="Use Multires Level As Is",
        default=False,
        description="Use the current multires level of the selected objects for the transpose target"
    )
    include_non_multires: bpy.props.BoolProperty(
        name="Include Non-Multires Objects",
        default=False,
        description="Include objects that do not have a multires modifier in the transpose target"
    )
    hide_original: bpy.props.BoolProperty(
        name="Hide Original Objects",
        default=True,
        description="Hide the original objects after creating the transpose target"
    )

    def execute(self, context):
        start_time = time.time()
        multires_level = self.multires_level if not self.use_multires_level_as_is else None
        transpose_target, merged_objs = copy_multires_objs_to_new_mesh(context, context.selected_objects, multires_level, self.include_non_multires)
        transpose_target.name = TRANSPOSE_TARGET_NAME

        for obj in context.selected_objects:
            obj.select_set(False)

        if self.hide_original:
            for obj in merged_objs:
                obj.hide_set(True)

        context.view_layer.objects.active = transpose_target
        transpose_target.select_set(True)

        self.logger.info(f"Time taken to create Transpose Target: {time.time() - start_time}")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Settings:", icon="SETTINGS")

        col.prop(self, "use_multires_level_as_is", text="Use Multires Level As Is")
        col.prop(self, "include_non_multires", text="Include Non-Multires Objects")
        col.prop(self, "hide_original", text="Hide Original Objects")

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

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        default=0.01,
        min=0.0,
        step=0.01,
        description="Threshold for the difference between the original mesh and the transpose target mesh. Only used if Auto Iterations is enabled"
    )
    auto_iterations: bpy.props.BoolProperty(
        name="Auto Iterations",
        default=False,
        description="Automatically apply reshape until the threshold is reached."
    )
    max_auto_iterations: bpy.props.IntProperty(name="Max Auto Iterations", default=100, min=1)
    iterations: bpy.props.IntProperty(
        name="Max Iterations",
        default=1,
        min=1,
        description="Maximum number of iterations to apply reshape. Only used if Auto Iterations is disabled"
    )
    hide_transpose: bpy.props.BoolProperty(
        name="Hide Transpose Target",
        default=False,
        description="Hide the transpose target after applying it"
    )

    def execute(self, context):
        start_time = time.time()

        active_obj = context.active_object
        if active_obj.name != TRANSPOSE_TARGET_NAME:
            self.report({'WARNING'}, f"Selected object does not have name {TRANSPOSE_TARGET_NAME}, operation may fail")

        # Create individual mesh objects as targets for the multires modifier's reshape operation
        transpose_targets = create_meshes_by_original_name(active_obj)
        self.logger.debug(f"Created {len(transpose_targets)} transpose targets")

        for object in transpose_targets:
            # Parse the original object name from the transpose target name
            original_obj_name = ""
            original_obj_name = object.name[:-len("_Target")]
            if original_obj_name not in bpy.data.objects:
                self.logger.warn(f"Object {object.name} does not have original object name recorded, skipping")
                continue

            original_obj = bpy.data.objects[original_obj_name]
            # Make sure that it shows in the depsgraph
            original_obj.hide_set(False)

            with bmesh_from_obj(object, write_back=False) as bm:
                # A mesh after being split is not guaranteed to have the same vertex indices as the original mesh
                restore_vertex_index(bm)
                # Apply the inverse transformation of the original object because the original transformation
                # was applied when the transpose target was created
                bmesh.ops.transform(bm, verts=bm.verts, matrix=original_obj.matrix_world.inverted())
                # Read the original multires level used to create this transpose target
                original_multires_level = read_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_SUBDIVISION_LEVEL_LAYER, uniform=True)

                # Use the reshape operator to apply the transpose target if the original multires level is greater than 0
                if original_multires_level > 0:
                    diff = self.threshold + 1
                    last_diff = iteration = 0

                    # Apply edits to the bmesh object for use with the reshape operator
                    bm.to_mesh(object.data)

                    with bpy.context.temp_override(object=original_obj, selected_editable_objects=(original_obj, object)):
                        multires_modifier = original_obj.modifiers[0]
                        current_level = multires_modifier.levels

                        # Set the multires level to the original multires level used to create the transpose target
                        multires_modifier.levels = original_multires_level
                        if not self.auto_iterations:
                            for _ in range(self.iterations):
                                bpy.ops.object.multires_reshape(modifier=multires_modifier.name)
                        else:
                            while diff > self.threshold and (abs(diff - last_diff) > 0.00001) and iteration < self.max_auto_iterations:
                                bpy.ops.object.multires_reshape(modifier=multires_modifier.name)

                                # Calculate difference between the original mesh and the transpose target mesh
                                multires_mesh = context.evaluated_depsgraph_get().objects[original_obj.name].data
                                verts = np.array([v.co for v in multires_mesh.vertices])
                                new_verts = np.array([v.co for v in bm.verts])
                                last_diff = diff
                                diff = np.abs(verts - new_verts).max()

                                iteration += 1

                            self.logger.debug(
                                f"\n*************Auto Rehape Iteration for Object {original_obj.name} Ended With:*************\n"
                                f"{'Threshold:':<15}{self.threshold}\n"
                                f"{'Diff:':<15}{diff}\n"
                                f"{'Last Diff:':<15}{last_diff}\n"
                                f"{'Iteration:':<15}{iteration}/{self.max_auto_iterations}"
                            )
                        multires_modifier.levels = current_level
                # Directly copy vertex coordinates if the original multires level is 0 or if the original object
                # has no multires modifier, in which case the original_multires_level will be -1
                else:
                    with bmesh_from_obj(original_obj) as obm:
                        bmesh_copy_vert_location(bm, obm)
        # Cleanup targets
        for obj in transpose_targets:
            bpy.data.objects.remove(obj, do_unlink=True, do_id_user=True, do_ui_user=True)

        if self.hide_transpose:
            active_obj.hide_set(True)

        self.logger.debug(f"Time taken to apply Transpose Target: {time.time() - start_time}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Settings:", icon="SETTINGS")

        col.prop(self, "auto_iterations", text="Auto Iterations. This may take a long time to finish")
        col.prop(self, "hide_transpose", text="Hide Transpose Target")

        if self.auto_iterations:
            row = col.row()
            row.prop(self, "threshold", text="Threshold")
            row.prop(self, "max_auto_iterations", text="Max Auto Iterations")
        else:
            row = col.row()
            row.prop(self, "iterations", text="Reshape Iterations")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, MULTIRES_TRANSPOSE_OT_apply_transpose_target)

register, unregister = bpy.utils.register_classes_factory(classes)
