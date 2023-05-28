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
    bl_label = "Create Multires Tranpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start_time = time.time()

        transpose_target = copy_multires_objs_to_new_mesh(context, context.selected_objects, 2)
        transpose_target.name = "Multires_Transpose_Target"

        for obj in context.selected_objects:
            obj.select_set(False)
        context.view_layer.objects.active = transpose_target
        transpose_target.select_set(True)

        self.logger.info(f"Time taken to create Tranpose Target: {time.time() - start_time}")
        return {"FINISHED"}


class MULTIRES_TRANPOSE_OT_apply_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.apply_transpose_target"
    bl_label = "Apply Multires Tranpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        THRESHOLD = 0.01
        MAX_ITERATIONS = 50
        use_iteration = False
        active_obj = context.active_object
        if active_obj.name != "Multires_Transpose_Target":
            self.report({'WARNING'}, "Selected object does not have name 'Multires_Transpose_Target', operation may fail")

        tranpose_targets = split_meshes_by_original_name(active_obj)
        for object in tranpose_targets:
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

                bm.to_mesh(object.data)
                selected_objs = (original_obj, object)
                diff = THRESHOLD + 1
                last_diff = 0
                iteration = 0
                with bpy.context.temp_override(object=original_obj, selected_editable_objects=selected_objs):
                    if use_iteration:
                        for _ in range(5):
                            bpy.ops.object.multires_reshape(modifier="Multires")
                    else:
                        while diff > THRESHOLD and (abs(diff - last_diff) > 0.0000000000000001) and iteration < MAX_ITERATIONS:
                            bpy.ops.object.multires_reshape(modifier="Multires")

                            depsgraph = context.evaluated_depsgraph_get()
                            multires_mesh = depsgraph.objects[original_obj.name].data
                            verts = np.array([v.co for v in multires_mesh.vertices])
                            new_verts = np.array([v.co for v in bm.verts])
                            last_diff = diff
                            diff = np.abs(verts - new_verts).max()
                            iteration += 1

                bmesh.ops.transform(bm, verts=bm.verts, matrix=original_obj.matrix_world)

        # Remove all transpose targets
        for obj in tranpose_targets:
            bpy.data.objects.remove(obj)

        return {'FINISHED'}


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, MULTIRES_TRANPOSE_OT_apply_transpose_target)

register, unregister = bpy.utils.register_classes_factory(classes)
