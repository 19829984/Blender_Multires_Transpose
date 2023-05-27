import bmesh
from ..data_types import MeshDomain, MeshLayerType
from typing import Iterable, Any


def resolve_domain_and_layer_type(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str):
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


def write_layer_data(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str, data: Iterable[Any]):
    """
    Write custom data to a mesh's layer at one of its types, create the layer if it doesn't exist.

    Args:
        bm (bmesh.types.BMesh): bmesh object to write to
        domain (MeshDomain): Domain to read from
        layer_type (MeshLayerType): Layer type to read from
        layer_name (str): Name of the layer to write to
        data (Iterable[Any]): Data to write
    """
    dom, layer = resolve_domain_and_layer_type(bm, domain, layer_type, layer_name)

    # Check if data contains string data and encode them to bytes
    if data and isinstance(data[0], str):
        data = [bytes(d, "utf-8") for d in data]

    for dat, dom_elemnt in zip(data, dom):
        dom_elemnt[layer] = dat


def read_layer_data(bm: bmesh.types.BMesh, domain: MeshDomain, layer_type: MeshLayerType, layer_name: str, uniform: bool = False):
    """
    Read custom data from a mesh's layer at one of its types, create the layer if it doesn't exist.

    Args:
        bm (bmesh.types.BMesh): bmesh object to read from
        domain (MeshDomain): Domain to read from
        layer_type (MeshLayerType): Layer type to read from
        layer_name (str): Name of the layer to read from
        uniform (bool, optional): Whether the data is expected to be uniform. Defaults to False.

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

    data = [dom_elemnt[layer] for dom_elemnt in dom]

    # Check if data contains string data and decode them to strings
    if data and isinstance(data[0], bytes):
        data = [d.decode("utf-8") for d in data]

    return data
