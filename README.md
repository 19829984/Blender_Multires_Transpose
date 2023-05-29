# Multires Transpose
An addon inspired by ZBrush's Transpose Master Plugin. It aims to mimic its functionality by allowing the user to edit an arbitrary number of multiresolution modifier-enabled meshes at once through a single lower subdivision level mesh, with support for objects with different subdivison levels, as well as meshes without the multires modifier.


## Features:
Multires Tranpose Version 1.0.0:
* Allows editing an arbitrary number of multiresolution modifier-enabled meshes at once through creating a single lower subdivision level proxy mesh.
    * This proxy mesh can be created through the Create Transpose Target operator
    * Supports using objects with different subdivision levels, or the same level for all objects
    * Can optionally include meshes not using the multires modifier
        * The proxy mesh for this will use the original mesh without any modifiers applied
* Changes to the proxy mesh can be propagated back to the original meshes with the Apply Transpose Target operator
    * The makes use of the multires modifier's reshape operator, which may not propagate the changes with 100% accuracy.
    * Therefore you can specify the number of iterations to apply the reshape operator to improve the accuracy of the changes
        * Use auto iteration to automatically reshape the mesh until the changes are within a specified threshold, or until the specified number of iterations have been reached
