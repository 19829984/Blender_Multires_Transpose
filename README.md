# Multires Transpose
An addon inspired by ZBrush's Transpose Master Plugin. It aims to mimic its functionality by allowing the user to edit an arbitrary number of multiresolution modifier-enabled meshes at once through a single lower subdivision level mesh, with support for objects with different subdivison levels, as well as meshes without the multires modifier.

Requires Blender 3.0 or later.

## How to use:
UI Panel located in the sidebar of the 3D viewport under `Multires Transpose`
1. Select meshes to create a Transpose Target proxy mesh for
2. Click `Create Transpose Target` to create a proxy mesh
3. Make changes to the proxy mesh
4. Click `Apply Transpose Target` to apply the changes to the original meshes

## Features:
Multires Tranpose Version 1.0.2:
* Allows editing an arbitrary number of multiresolution modifier-enabled meshes at once through creating a single lower subdivision level proxy mesh.
    * This proxy mesh can be created through the Create Transpose Target operator
    * Supports using objects with different subdivision levels, or the same level for all objects
    * Can optionally include meshes not using the multires modifier
        * The proxy mesh for this will use the original mesh without any modifiers applied
* Changes to the proxy mesh can be propagated back to the original meshes with the Apply Transpose Target operator
    * Modifiers can be used on the proxy mesh, this allows you to rig the proxy mesh or use other modifiers.
    * The makes use of the multires modifier's reshape operator, which may not propagate the changes with 100% accuracy.
    * Therefore you can specify the number of iterations to apply the reshape operator to improve the accuracy of the changes
        * Use auto iteration to automatically reshape the mesh until the changes are within a specified threshold, or until the specified number of iterations have been reached
* Multiple Transpose Targets can be created to store different poses.

### Known Limitations
Facesets may not be preserved when creating the transpose target
Does not work with multiuser data (instancing)
