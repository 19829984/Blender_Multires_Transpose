import bmesh
from ..data_types import MeshDomain, MeshLayerType
from typing import Iterable, Any
import operator

ALL_DOMAINS = {'faces', 'edges', 'verts', 'loops'}
ALL_POSSIBLE_LAYERS = {'bevel_weight', 'int', 'paint_mask', 'float_color', 'string', 'freestyle', 'skin', 'float_vector', 'uv', 'shape', 'deform', 'crease', 'face_map', 'color', 'float'}
GET_LAYER_FNS = [operator.attrgetter(f'{domain}.layers') for domain in ALL_DOMAINS]


def resolve_domain_and_layer_type(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str) -> tuple[bmesh.types.BMElemSeq, Any]:
    """
    Resolve the domain and layer type to the corresponding bmesh domain and layer type

    Args:
        bm (bmesh.types.BMesh): bmesh object to resolve domain and layer type on
        domain (MeshDomain): domain where the data is stored
        layer_type (MeshLayerType): type of the data
        layer_name (str): name of the data layer

    Returns:
        dom, layer: resolved domain and layer object
    """
    match domain:
        case MeshDomain.FACES:
            dom = bm.faces
        case MeshDomain.LOOPS:
            dom = bm.loops
        case MeshDomain.EDGES:
            dom = bm.edges
        case MeshDomain.VERTS:
            dom = bm.verts

    match layer_type:
        case MeshLayerType.STRING:
            layer = dom.layers.string.get(layer_name, None)
            if not layer:
                layer = dom.layers.string.new(layer_name)
        case MeshLayerType.INT:
            layer = dom.layers.int.get(layer_name, None)
            if not layer:
                layer = dom.layers.int.new(layer_name)
        case MeshLayerType.FLOAT:
            layer = dom.layers.float.get(layer_name, None)
            if not layer:
                layer = dom.layers.float.new(layer_name)
        case MeshLayerType.FLOAT_VECTOR:
            layer = dom.layers.float_vector.get(layer_name, None)
            if not layer:
                layer = dom.layers.float_vector.new(layer_name)

    return dom, layer


def write_layer_data(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str, data: Iterable[Any], start_index: int = 0) -> None:
    """
    Write custom data to a mesh's layer at one of its types, create the layer if it doesn't exist.

    Args:
        bm (bmesh.types.BMesh): bmesh object to write to
        domain (MeshDomain): Domain to read from
        layer_type (MeshLayerType): Layer type to read from
        layer_name (str): Name of the layer to write to
        data (Iterable[Any]): Data to write
        start_index (int, optional): Index to start writing data from. Defaults to 0.
    """
    dom, layer = resolve_domain_and_layer_type(bm, domain, layer_type, layer_name)

    # Check if data contains string data and encode them to bytes
    if data and isinstance(data[0], str):
        data = [bytes(d, "utf-8") for d in data]

    for dat, dom_elemnt in zip(data, dom[start_index:len(data)]):
        dom_elemnt[layer] = dat


def read_layer_data(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str, uniform: bool = False, start_index: int = 0, size: int = None) -> Iterable[Any]:
    """
    Read custom data from a mesh's layer at one of its types, create the layer if it doesn't exist.

    Args:
        bm (bmesh.types.BMesh): bmesh object to read from
        domain (MeshDomain): Domain to read from
        layer_type (MeshLayerType): Layer type to read from
        layer_name (str): Name of the layer to read from
        uniform (bool, optional): Whether the data is expected to be the same across the mesh. Defaults to False.
        start_index (int, optional): Index to start reading data from. Defaults to 0.
        size (int, optional): Number of data to read. Defaults to None.

    Returns:
        Iterable[Any]: Data read
    """
    dom, layer = resolve_domain_and_layer_type(bm, domain, layer_type, layer_name)

    if uniform:
        # Early exit on uniform data
        for dom_elemnt in dom:
            data = dom_elemnt[layer]
            if data and isinstance(data, bytes):
                return data.decode("utf-8")
            return data

    data = [dom_elemnt[layer] for dom_elemnt in dom[start_index:size]]

    # Check if data contains string data and decode them to strings
    if data and isinstance(data[0], bytes):
        data = [d.decode("utf-8") for d in data]

    return data


def copy_all_layers(src_bmesh: bmesh.types.BMesh, dst_bmesh: bmesh.types.BMesh) -> None:
    """
    Copy all layers from src_bmesh to dst_bmesh

    Args:
        src_bmesh (bmesh.types.BMesh): bmesh to copy from
        dst_bmesh (bmesh.types.BMesh): bmesh to copy to
    """
    for get_layers in GET_LAYER_FNS:
        layers = get_layers(src_bmesh)  # equivalent to src_bmesh.{domain}.layers
        layer_names = [available_layer for available_layer in dir(layers) if available_layer in ALL_POSSIBLE_LAYERS]

        get_layer_attr_fns = [operator.attrgetter(layer) for layer in layer_names]
        for get_layer_attr in get_layer_attr_fns:
            attrs = get_layer_attr(layers)  # equivalent to src_bmesh.{domain}.layers.{layer}

            # For loop filters out empty layers
            for name, _ in attrs.items():
                get_layer_attr(get_layers(dst_bmesh)).new(name)


def bmesh_from_faces(src_bmesh: bmesh.types.BMesh, faces: Iterable[bmesh.types.BMFace]) -> bmesh.types.BMesh:
    """
    Create a new bmesh from a given sequence of faces from the given src_bmesh

    Args:
        src_bmesh (bmesh.types.BMesh): source bmesh to copy from
        faces (Iterable[bmesh.types.BMFace]): faces to copy

    Returns:
        bmesh.types.BMesh: new bmesh containing the given faces
    """

    dst_bmesh = bmesh.new()
    copy_all_layers(src_bmesh, dst_bmesh)
    min_vert_index = min([v.index for f in faces for v in f.verts])

    # Copy vertices and assign correct indices
    accessed_indices = set()
    for face in faces:
        for v in face.verts:
            if v.index not in accessed_indices:
                nv = dst_bmesh.verts.new(v.co, v)
                nv.index = v.index - min_vert_index
                accessed_indices.add(v.index)
    dst_bmesh.verts.sort()
    dst_bmesh.verts.index_update()
    dst_bmesh.verts.ensure_lookup_table()

    # Copy faces
    for face in faces:
        dst_bmesh.faces.new(tuple(dst_bmesh.verts[v.index - min_vert_index] for v in face.verts), face)
    dst_bmesh.faces.index_update()
    dst_bmesh.faces.sort()

    return dst_bmesh


def bmesh_join(list_of_bmeshes: Iterable[bmesh.types.BMesh], normal_update=False) -> bmesh.types.BMesh:
    """ takes as input a list of bm references and outputs a single merged bmesh
    allows an additional 'normal_update=True' to force _normal_ calculations.
    Modified from https://blender.stackexchange.com/questions/50160/scripting-low-level-join-meshes-elements-hopefully-with-bmesh
    """

    bm = bmesh.new()
    add_vert = bm.verts.new
    add_face = bm.faces.new
    add_edge = bm.edges.new

    copy_all_layers(list_of_bmeshes[0], bm)

    for bm_to_add in list_of_bmeshes:
        offset = len(bm.verts)

        for v in bm_to_add.verts:
            add_vert(v.co, v)

        bm.verts.index_update()
        bm.verts.ensure_lookup_table()

        if bm_to_add.faces:
            for face in bm_to_add.faces:
                add_face(tuple(bm.verts[i.index + offset] for i in face.verts), face)
            bm.faces.index_update()

        if bm_to_add.edges:
            for edge in bm_to_add.edges:
                edge_seq = tuple(bm.verts[i.index + offset] for i in edge.verts)
                try:
                    add_edge(edge_seq, edge)
                except ValueError:
                    # edge exists!
                    pass
            bm.edges.index_update()

    if normal_update:
        bm.normal_update()

    return bm


def bmesh_copy_vert_location(src_bmesh, dst_bmesh):
    """
    Copy the vertex locations from src_bmesh to dst_bmesh by vertex indieces.
    Both must have the same number of vertices.

    Args:
        src_bmesh (bmesh.types.BMesh): source bmesh to copy from
        dst_bmesh (bmesh.types.BMesh): destination bmesh to copy to
    """
    if len(src_bmesh.verts) != len(dst_bmesh.verts):
        raise ValueError("src_bmesh and dst_bmesh must have the same number of vertices")

    for src_v, dst_v in zip(src_bmesh.verts, dst_bmesh.verts):
        dst_v.co = src_v.co
