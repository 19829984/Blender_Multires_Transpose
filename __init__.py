# Check if addon is being reloaded
# This also allows script.reload() to reload the addon
if "multires_transpose" not in locals():
    from . import multires_transpose
else:
    import importlib
    multires_transpose = importlib.reload(multires_transpose)

modules = [multires_transpose]

bl_info = {
    "name": "Multires Transpose",
    "author": "Bowen Wu",
    "description": "Allow editing an arbitrary number of multiresolution modifier-enabled meshes at once through a single lower subdivision level mesh, with support for objects with different subdivison levels.",
    "blender": (3, 0, 0),
    "version": (1, 0, 0),
    "location": "",
    "warning": "",
    "category": "Sculpting"
}


def register():
    for module in modules:
        module.register()


def unregister():
    for module in modules[::-1]:
        module.unregister()
