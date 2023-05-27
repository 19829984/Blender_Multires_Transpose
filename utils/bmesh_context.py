import bmesh
import contextlib

@contextlib.contextmanager
def bmesh_from_obj(obj):
    mesh_data = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    yield bm
    bm.to_mesh(mesh_data)
    bm.free()
