import bmesh
import contextlib


@contextlib.contextmanager
def bmesh_from_obj(obj, write_back=True):
    mesh_data = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    yield bm
    if write_back:
        bm.to_mesh(mesh_data)
    bm.free()
