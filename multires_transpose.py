import bpy
from typing import Iterable, List, Any
import bmesh
import time
import logging
from .data_types import MeshDomain, MeshLayerType
from .utils.bmesh_layer_ops import write_layer_data, read_layer_data
from .utils.bmesh_context import bmesh_from_obj

ORIGINAL_OBJECT_NAME_LAYER = "original_object_name"
ORIGINAL_VERTEX_INDEX_LAYER = "original_vertex_index"


class LoggerOperator(bpy.types.Operator):
    def __init__(self):
        self.logger = logging.getLogger(__name__ + "." + self.__class__.__name__)


def set_multires_to_first_level(objects: Iterable[bpy.types.Object]):
    """
    set all selected object's multiresolution modifier's view subdivision level to the first level

    Args:
        objects (Iterable[bpy.types.Object]): Objects to change multires level on

    Returns:
        set[bpy.types.Object]: Objects that have had they multires level changed
    """
    changed_objs = set()
    for obj in objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "MULTIRES":
                    mod.levels = 1
                    changed_objs.add(obj)
                    break

    return changed_objs


def duplicate(obj: bpy.types.Object, data: bool = True, actions: bool = True, collection: bpy.types.Collection = None):
    """
    Duplicate an object, including its data and animation data
    From: https://b3d.interplanety.org/en/making-a-copy-of-an-object-using-the-blender-python-api/

    Args:
        obj (bpy.types.Object): object to duplicate
        data (bool, optional): duplicate data. Defaults to True.
        actions (bool, optional): duplicate actions. Defaults to True.
        collection (bpy.types.Collection, optional): collection to link to. Defaults to None.

    Returns:
        bpy.types.Object: duplicated object
    """
    obj_copy = obj.copy()
    if data:
        obj_copy.data = obj_copy.data.copy()
    if actions and obj_copy.animation_data:
        obj_copy.animation_data.action = obj_copy.animation_data.action.copy()
    collection.objects.link(obj_copy)
    return obj_copy


def duplicate_mesh_objects(context: bpy.types.Context, objects: Iterable[bpy.types.Object], suffix: str = "_copy"):
    """
    Duplicate objects in the scene

    Args:
        context (bpy.types.Context): Context to get depsgraph from
        objects (Iterable[bpy.types.Object]): Objects to duplicate
        suffix (str, optional): Suffix to append to the name of the duplicated objects. Defaults to "_copy".

    Returns:
        set[bpy.types.Object]: Objects that have been duplicated
    """
    new_objs = set()
    for obj in objects:
        if obj.type == "MESH":
            new_obj = duplicate(obj=obj, collection=context.collection)
            # Set name of new object to be the same as the old object with a suffix _copy
            new_obj.name = obj.name + suffix

            new_objs.add(new_obj)

    return new_objs


def record_required_data(context: bpy.types.Context, objects: Iterable[bpy.types.Object], original_objects: Iterable[bpy.types.Object]):
    """
    Record the required data of the given objects

    Args:
        context (bpy.types.Context): Context to get depsgraph from
        objects (Iterable[bpy.types.Object]): Objects to record required data on
        original_objects (Iterable[bpy.types.Object]): Original objects to record required data from
    """
    for object, original_object in zip(objects, original_objects):
        with bmesh_from_obj(object) as bm:
            # Record the original object names in the new object's face layer
            write_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, [original_object.name for f in bm.faces])

            # Record the original vertex indices in the new object's vertex layer
            depsgraph = context.evaluated_depsgraph_get()
            multires_mesh = depsgraph.objects[original_object.name].data
            write_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_VERTEX_INDEX_LAYER, [v.index for v in multires_mesh.vertices])

            # Record the original object's origin in the new object's vertex layer
            write_layer_data(bm, MeshDomain.VERTS, MeshLayerType.FLOAT_VECTOR, "original_object_origin", [original_object.location for v in bm.verts])


def restore_vertex_index(bm: bmesh.types.BMesh):
    """
    Restore the vertex indices of the given object to the original vertex indices

    Args:
        object (bpy.types.Object): Object to restore vertex indices on
    """
    original_vertex_indices = read_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_VERTEX_INDEX_LAYER)
    for v, original_index in zip(bm.verts, original_vertex_indices):
        v.index = original_index
    bm.verts.sort()


def restore_object_origin(bm: bmesh.types.BMesh):
    """
    Restore the object origin of the given object to the original object origin

    Args:
        object (bpy.types.Object): Object to restore object origin on

    Returns:
        Vector: Original object origin
    """
    original_object_origins = read_layer_data(bm, MeshDomain.VERTS, MeshLayerType.FLOAT_VECTOR, "original_object_origin", uniform=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=-original_object_origins)
    return original_object_origins


def restore_recorded_data(object: bpy.types.Object):
    """
    Restore the recorded data on the given object

    Args:
        object (bpy.types.Object): Object to restore recorded data on
    """
    with bmesh_from_obj(object) as bm:
        restore_vertex_index(bm)
        original_origin = restore_object_origin(bm)
    object.location += original_origin


def merge_objects(objects: List[bpy.types.Object]):
    """
    Merge the given objects into a single object

    Args:
        objects (List[bpy.types.Object]): Objects to merge

    Returns:
        bpy.types.Object: Merged object
    """
    if len(objects) < 2:
        return None

    with bpy.context.temp_override(active_object=objects[0], selected_editable_objects=objects):
        # Merge objects
        bpy.ops.object.join()

        return bpy.context.active_object


def apply_modifiers(objects: Iterable[bpy.types.Object]):
    """
    Apply all modifiers on the given objects

    Args:
        objects (Iterable[bpy.types.Object]): Objects to apply modifiers on
    """
    for object in objects:
        with bpy.context.temp_override(object=object):
            for mod in object.modifiers:
                bpy.ops.object.modifier_apply(modifier=mod.name)


# def separate_mesh_by_original_object_name(bm: bmesh.types.BMesh):


class MULTIRES_TRANSPOSE_OT_create_transpose_target(LoggerOperator):
    bl_idname = "multires_transpose.create_transpose_target"
    bl_label = "Create Multires Tranpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start_time = time.time()

        objs = set_multires_to_first_level(context.selected_objects)
        new_objs = duplicate_mesh_objects(context, objs)
        set_multires_to_first_level(new_objs)
        apply_modifiers(new_objs)
        record_required_data(context, new_objs, objs)
        merged_obj = merge_objects(list(new_objs))
        merged_obj.name = "Multires_Transpose_Target"

        for obj in objs:
            obj.select_set(False)
        context.view_layer.objects.active = merged_obj
        merged_obj.select_set(True)

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

        # TODO: Separate objects based on original object name
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.separate(type="LOOSE")
        bpy.ops.object.editmode_toggle()

        separated_objects = context.selected_objects
        for object in separated_objects:
            original_obj_name = ""
            with bmesh_from_obj(object) as bm:
                original_obj_name = read_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, uniform=True)
            if not original_obj_name:
                self.logger.warn(f"Object {object.name} does not have original object name recorded, skipping")
                continue
            original_obj = bpy.data.objects[original_obj_name]

            restore_recorded_data(object)
            selected_objs = (original_obj, object)
            with bpy.context.temp_override(object=original_obj, selected_editable_objects=selected_objs):
                # TODO: Auto iteration count
                for _ in range(iters):
                    bpy.ops.object.multires_reshape(modifier="Multires")

        # Join objects back together
        merged_obj = merge_objects(tuple(separated_objects))
        merged_obj.name = "Multires_Transpose_Target"

        return {'FINISHED'}


class TestOperator(bpy.types.Operator):
    bl_idname = "multires_transpose.test_operator"
    bl_label = "Test Operator"

    def execute(self, context):
        obj = context.active_object
        restore_vertex_index(obj)

        return {"FINISHED"}


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, TestOperator, MULTIRES_TRANPOSE_OT_apply_transpose_target)

register, unregister = bpy.utils.register_classes_factory(classes)
