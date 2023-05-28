import bpy
from typing import Iterable, List, Any
import bmesh
import time
import logging
from .data_types import MeshDomain, MeshLayerType
from .utils.bmesh_utils import write_layer_data, read_layer_data, bmesh_join, bmesh_from_faces
from .utils.bmesh_context import bmesh_from_obj

ORIGINAL_OBJECT_NAME_LAYER = "original_object_name"
ORIGINAL_VERTEX_INDEX_LAYER = "original_vertex_index"


class LoggerOperator(bpy.types.Operator):
    def __init__(self):
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)


def set_multires_to_nth_level(objects: Iterable[bpy.types.Object], n: int) -> set[bpy.types.Object]:
    """
    set all selected object's multiresolution modifier's view subdivision level to the first level

    Args:
        objects (Iterable[bpy.types.Object]): Objects to change multires level on
        n (int): Level to set multires to

    Returns:
        set[bpy.types.Object]: Objects that have had they multires level changed
    """
    changed_objs = set()
    for obj in objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "MULTIRES":
                    mod.levels = n
                    changed_objs.add(obj)
                    break

    return changed_objs


def restore_vertex_index(bm: bmesh.types.BMesh) -> None:
    """
    Restore the vertex indices of the given object to the original vertex indices

    Args:
        object (bpy.types.Object): Object to restore vertex indices on
    """
    original_vertex_indices = read_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_VERTEX_INDEX_LAYER)
    for v, original_index in zip(bm.verts, original_vertex_indices):
        v.index = original_index
    bm.verts.sort()


def split_meshes_by_original_name(object: bpy.types.Object) -> List[bpy.types.Object]:
    """
    Split the given object into multiple objects based on the original object name recorded in the mesh's face layer

    Args:
        object (bpy.types.Object): Object to split

    Returns:
        List[bpy.types.Object]: List of split objects
    """
    split_objects = []

    with bmesh_from_obj(object) as bm:
        original_obj_names = read_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, uniform=False)
        tranpose_map = {name: [] for name in set(original_obj_names)}

        # Create a map of original object names to faces
        for face, name in zip(bm.faces, original_obj_names):
            tranpose_map[name].append(face)

        for obj_name, faces in tranpose_map.items():
            face_index_min = min([f.index for f in faces])
            face_index_max = max([f.index for f in faces])

            # Create a new bmesh from the faces associated with the original object
            d_bm = bmesh_from_faces(bm, bm.faces[face_index_min:face_index_max + 1])
            temp_mesh = bpy.data.meshes.new(name=f"{obj_name}_tgt")
            d_bm.to_mesh(temp_mesh)
            d_bm.free()

            # Create object from mesh and link it
            tmp_obj = bpy.data.objects.new(name=f"{obj_name}_Target", object_data=temp_mesh)
            bpy.context.collection.objects.link(tmp_obj)
            split_objects.append(tmp_obj)

    return split_objects


def copy_multires_objs_to_new_mesh(context: bpy.types.Context, objects: Iterable[bpy.types.Object], level: int = 1) -> bpy.types.Object:
    """
    Copy all objects to a new mesh at the given multires level, if they have a multires modifier.

    Args:
        context (bpy.types.Context): context
        objects (Iterable[bpy.types.Object]): objects to copy from
        level (int, optional): Multires subdivision level. Defaults to 1.

    Returns:
        bpy.types.Object: merged object
    """
    # Create new mesh and object, then link it
    transpose_target_mesh = bpy.data.meshes.new(name="Multires_Transpose_Target")

    set_multires_to_nth_level(objects, level)
    depsgraph = context.evaluated_depsgraph_get()

    bms = []

    for object in objects:
        bm = bmesh.new()
        bm.from_mesh(depsgraph.objects[object.name].data)
        # Apply transformations to the mesh
        bmesh.ops.transform(bm, verts=bm.verts, matrix=object.matrix_world)

        # Record the original object names in the new object's face layer
        write_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, [object.name for f in bm.faces])

        # Record the original vertex indices in the new object's vertex layer
        write_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_VERTEX_INDEX_LAYER, [v.index for v in bm.verts])

        # Record the original object's origin in the new object's vertex layer
        write_layer_data(bm, MeshDomain.VERTS, MeshLayerType.FLOAT_VECTOR, "original_object_origin", [object.location for v in bm.verts])
        bms.append(bm)

    final_bm = bmesh.new()
    final_bm = bmesh_join(bms)
    final_bm.to_mesh(transpose_target_mesh)
    final_bm.free()

    transpose_target_obj = bpy.data.objects.new(name="Multires_Transpose_Target", object_data=transpose_target_mesh)
    context.collection.objects.link(transpose_target_obj)
    return transpose_target_obj


class MULTIRES_TRANSPOSE_OT_create_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.create_transpose_target"
    bl_label = "Create Multires Tranpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start_time = time.time()

        transpose_target = copy_multires_objs_to_new_mesh(context, context.selected_objects)
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
        iters = 5
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
                with bpy.context.temp_override(object=original_obj, selected_editable_objects=selected_objs):
                    # TODO: Auto iteration count
                    for _ in range(iters):
                        bpy.ops.object.multires_reshape(modifier="Multires")

                bmesh.ops.transform(bm, verts=bm.verts, matrix=original_obj.matrix_world)

        # Remove all transpose targets
        for obj in tranpose_targets:
            bpy.data.objects.remove(obj)

        return {'FINISHED'}


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, MULTIRES_TRANPOSE_OT_apply_transpose_target)

register, unregister = bpy.utils.register_classes_factory(classes)
