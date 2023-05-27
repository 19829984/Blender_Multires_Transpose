from enum import Enum


class MeshDomain(Enum):
    FACES = 1
    LOOPS = 2
    EDGES = 3
    VERTS = 4


class MeshLayerType(Enum):
    STRING = 1
    INT = 2
    FLOAT = 3
    FLOAT_VECTOR = 4
