import bpy
from typing import Iterable, Tuple
import bmesh

ORIGINAL_OBJECT_NAME_LAYER = "original_object_name"


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


def write_per_face_string(obj: bpy.types.Object, layer_name: str, data: Iterable[str]):
    """
    Write a string to a per-face layer of an object

    Args:
        obj (bpy.types.Object): Object to write to
        layer_name (str): Name of the layer to write to
        data (Iterable[str]): Data to write
    """
    mesh_data = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    str_layer = bm.faces.layers.string.get(layer_name, None)
    if not str_layer:
        str_layer = bm.faces.layers.string.new(layer_name)

    for f, s in zip(bm.faces, data):
        f[str_layer] = bytes(s, "utf-8")

    bm.to_mesh(mesh_data)
    bm.free()


def duplicate_objects(objects: Iterable[bpy.types.Object]):
    """
    Duplicate objects in the scene

    Args:
        objects (Iterable[bpy.types.Object]): Objects to duplicate

    Returns:
        set[bpy.types.Object]: Objects that have been duplicated
    """
    new_objs = set()
    for obj in objects:
        if obj.type == "MESH":
            new_obj = duplicate(obj=obj, collection=bpy.context.collection)
            # Set name of new object to be the same as the old object with a suffix _copy
            new_obj.name = obj.name + "_copy"
            # Write custom attribute to each vertex of the new object containing name of the original object
            write_per_face_string(new_obj, ORIGINAL_OBJECT_NAME_LAYER, [obj.name] * len(new_obj.data.polygons))

            new_objs.add(new_obj)

    return new_objs


def merge_objects(context, objects: Tuple[bpy.types.Object]):
    """
    Merge the given objects into a single object

    Args:
        objects (Tuple[bpy.types.Object]): Objects to merge

    Returns:
        bpy.types.Object: Merged object
    """
    if len(objects) < 2:
        return None

    with context.temp_override(area=context.area):
        # Clear selected objects
        bpy.ops.object.select_all(action="DESELECT")
        # Select all given objects
        for obj in objects:
            obj.select_set(True)
        # Set first object to be active object
        bpy.context.view_layer.objects.active = objects[0]

        # Merge objects
        bpy.ops.object.join()

        return bpy.context.view_layer.objects.active


def apply_modifiers(context: bpy.types.Context, objects: Iterable[bpy.types.Object]):
    """
    Apply all modifiers on the given objects

    Args:
        objects (Iterable[bpy.types.Object]): Objects to apply modifiers on
    """
    with context.temp_override(area=context.area):
        for object in objects:
            bpy.ops.object.select_all(action="DESELECT")
            context.view_layer.objects.active = object
            for mod in object.modifiers:
                bpy.ops.object.modifier_apply(modifier=mod.name)


class MULTIRES_TRANSPOSE_OT_create_transpose_target(bpy.types.Operator):
    bl_idname = "multires_transpose.create_transpose_target"
    bl_label = "Create Multires Tranpose Target"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        new_objs = duplicate_objects(context.selected_objects)
        objs = set_multires_to_first_level(new_objs)
        apply_modifiers(context, objs)
        merged_obj = merge_objects(context, tuple(objs))
        merged_obj.name = "Multires_Transpose_Target"
        return {"FINISHED"}

# Operator to print ORIGINAL_OBJECT_NAME_LAYER mesh data from the selected object


class TestOperator(bpy.types.Operator):
    bl_idname = "multires_transpose.test_operator"
    bl_label = "Test Operator"

    def execute(self, context):
        obj = context.active_object
        mesh_data = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh_data)
        str_layer = bm.faces.layers.string.get(ORIGINAL_OBJECT_NAME_LAYER)

        for f in bm.faces:
            print(f[str_layer])

        bm.free()

        return {"FINISHED"}


classes = (MULTIRES_TRANSPOSE_OT_create_transpose_target, TestOperator,)

register, unregister = bpy.utils.register_classes_factory(classes)
