import bpy


class MultiresTransposePanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Multires Transpose'


class MULTIRES_TRANSPOSE_PT_operator_panel(MultiresTransposePanel):
    bl_label = "Multires Transpose"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.operator(operator="multires_transpose.create_transpose_target", icon='MOD_MULTIRES')
        layout.operator(operator="multires_transpose.apply_transpose_target", icon='SHADERFX')


classes = (MULTIRES_TRANSPOSE_PT_operator_panel,)

register, unregister = bpy.utils.register_classes_factory(classes)
