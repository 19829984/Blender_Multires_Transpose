# Import all missing imports
import bpy
import bmesh
from typing import Iterable, List, Tuple
from .bmesh_context import bmesh_from_obj
from .bmesh_utils import write_layer_data, read_layer_data, bmesh_join, bmesh_from_faces
from ..data_types import MeshDomain, MeshLayerType

ORIGINAL_OBJECT_NAME_LAYER = "original_object_name"
ORIGINAL_VERTEX_INDEX_LAYER = "original_vertex_index"
ORIGINAL_SUBDIVISION_LEVEL_LAYER = "original_subdivision_level"


def set_multires_to_nth_level(objects: Iterable[bpy.types.Object], n: int | None) -> Tuple[set[bpy.types.Object], List[int]]:
    """
    set all selected object's multiresolution modifier's view subdivision level to the first level

    Args:
        objects (Iterable[bpy.types.Object]): Objects to change multires level on
        n (int | None): Level to set multires to. If None will use multires levels as they are

    Returns:
        set[bpy.types.Object], list[int]: Objects that have had they multires level changed, and their subdivision level
    """
    changed_objs = set()
    levels = []
    for obj in objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "MULTIRES":
                    if n is not None:
                        mod.levels = n
                    if obj not in changed_objs:
                        changed_objs.add(obj)
                        levels.append(mod.levels)
                    break
    return changed_objs, levels


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


def create_meshes_by_original_name(object: bpy.types.Object) -> List[bpy.types.Object]:
    """
    Split the given object into multiple objects based on the original object name recorded in the mesh's face layer.
    The given object's mesh is not modified.

    Args:
        object (bpy.types.Object): Object to split

    Returns:
        List[bpy.types.Object]: List of split objects
    """
    split_objects = []

    with bmesh_from_obj(object) as bm:
        original_obj_names = read_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, uniform=False)
        if not all(original_obj_names):
            raise ValueError("Object does not have original object names recorded on all faces, cannot split to transpose targets")
        transpose_map = {name: [] for name in set(original_obj_names)}

        # Create a map of original object names to faces
        for face, name in zip(bm.faces, original_obj_names):
            transpose_map[name].append(face)

        for obj_name, faces in transpose_map.items():
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


def copy_multires_objs_to_new_mesh(context: bpy.types.Context, objects: Iterable[bpy.types.Object], level: int | None = 1, use_non_multires: bool = False) -> Tuple[bpy.types.Object, List[bpy.types.Object]]:
    """
    Copy all objects to a new mesh at the given multires level, if they have a multires modifier.

    Args:
        context (bpy.types.Context): context
        objects (Iterable[bpy.types.Object]): objects to copy from
        level (int | None, optional): Multires subdivision level. Defaults to 1. If none will use
            multires levels as they are

    Returns:
        bpy.types.Object: merged object
        List[bpy.types.Object]: list of objects that were merged
    """
    def record_data_helper(bm, object, multires_level):
        # Apply transformations to the mesh
        bmesh.ops.transform(bm, verts=bm.verts, matrix=object.matrix_world)

        # Record the original object names in the new object's face layer
        write_layer_data(bm, MeshDomain.FACES, MeshLayerType.STRING, ORIGINAL_OBJECT_NAME_LAYER, [object.name for f in bm.faces])

        # Record the original vertex indices in the new object's vertex layer
        write_layer_data(bm, MeshDomain.VERTS, MeshLayerType.INT, ORIGINAL_VERTEX_INDEX_LAYER, [v.index for v in bm.verts])

        # Record the original subidivision level in the new object's face layer, or -1 if multires_level is None
        if multires_level is not None:
            write_layer_data(bm, MeshDomain.FACES, MeshLayerType.INT, ORIGINAL_SUBDIVISION_LEVEL_LAYER, [multires_level for f in bm.faces])
        else:
            write_layer_data(bm, MeshDomain.FACES, MeshLayerType.INT, ORIGINAL_SUBDIVISION_LEVEL_LAYER, [-1 for f in bm.faces])

    # Create new mesh and object, then link it
    transpose_target_mesh = bpy.data.meshes.new(name="Multires_Transpose_Target")

    multires_objs, multires_levels = set_multires_to_nth_level(objects, level)
    non_multires_objects = [obj for obj in objects if obj not in multires_objs]
    depsgraph = context.evaluated_depsgraph_get()

    final_bm = bmesh.new()
    merged_objs = []

    for i, object in enumerate(multires_objs):
        bm = bmesh.new()
        bm.from_mesh(depsgraph.objects[object.name].data)
        record_data_helper(bm, object, multires_levels[i])
        final_bm = bmesh_join([bm, final_bm])
        bm.free()
        merged_objs.append(object)
    if use_non_multires:
        for object in non_multires_objects:
            bm = bmesh.new()
            bm.from_mesh(object.data)
            record_data_helper(bm, object, None)
            final_bm = bmesh_join([bm, final_bm])
            bm.free()
            merged_objs.append(object)

    final_bm.to_mesh(transpose_target_mesh)
    final_bm.free()

    transpose_target_obj = bpy.data.objects.new(name="Multires_Transpose_Target", object_data=transpose_target_mesh)
    context.collection.objects.link(transpose_target_obj)
    return transpose_target_obj, merged_objs
