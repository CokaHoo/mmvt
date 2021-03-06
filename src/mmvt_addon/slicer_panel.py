import bpy

def _addon():
    return SlicerPanel.addon


def slice_brain():
    import glob
    coordinate = bpy.context.scene.cursor_location
    cut_type = bpy.context.scene.slicer_cut_type
    create_joint_brain_obj()
    # coordinate = list(D.screens['Default'].areas[3].spaces[0].cursor_location)
    optional_cut_types = ['sagital', 'coronal', 'axial']
    optional_rots = [[1.5708, 0, 1.5708], [1.5708, 0, 3.14], [0, 3.14, 0]]
    option_ind = optional_cut_types.index(cut_type)
    bpy.context.scene.is_sliced_ind = option_ind
    bpy.context.scene.last_cursor_location = coordinate
    cut_pos = [0.0, 0.0, 0.0]
    cut_pos[option_ind] = coordinate[option_ind]
    print('rot={}'.format(optional_rots[option_ind]))
    if bpy.data.objects.get('{}_plane'.format(cut_type)) is None:
        bpy.ops.mesh.primitive_plane_add(radius=25.7 / 2.0, location=tuple(cut_pos))
        bpy.context.object.name = '{}_plane'.format(cut_type)
        bpy.context.object.rotation_euler = optional_rots[option_ind]
        bpy.ops.mesh.uv_texture_add()
    else:
        bpy.data.objects['{}_plane'.format(cut_type)].hide = False
        bpy.data.objects['{}_plane'.format(cut_type)].hide_render = False
    optional_cut_types.remove(cut_type)
    for cut in optional_cut_types:
        if bpy.data.objects.get('{}_plane'.format(cut)):
            bpy.data.objects['{}_plane'.format(cut)].hide = True
            bpy.data.objects['{}_plane'.format(cut)].hide_render = True


    cur_plane_obj = bpy.data.objects['{}_plane'.format(cut_type)]
    cur_plane_obj.location = tuple(cut_pos)
    images_path = 'mri_{}.png'.format(cut_type)
    # slice_image_path = glob.glob('{}*{}*'.format(images_path, cut_type))
    slice_image = bpy.data.images[images_path]
    cur_plane_obj.data.uv_textures['UVMap'].data[0].image = slice_image
    if bpy.data.objects.get('masking_cube') is None:
        bpy.ops.mesh.primitive_cube_add(radius=10)
        bpy.context.object.name = 'masking_cube'
    cube_location = [0, 0, 0]
    if cut_pos[option_ind] > 0 or cut_type == 'axial':
        cube_location[option_ind] = cut_pos[option_ind] + 9.99
    elif cut_pos[option_ind] < 0:
        cube_location[option_ind] = cut_pos[option_ind] - 9.99
    bpy.data.objects['masking_cube'].location = tuple(cube_location)
    bpy.data.objects['masking_cube'].hide = True
    bpy.data.objects['masking_cube'].hide_render = True
    for hemi in ['lh', 'rh']:
        inflated_object = bpy.data.objects['inflated_{}'.format(hemi)]
        if inflated_object.modifiers.get('mask_for_slice') is None:
            inflated_object.modifiers.new('mask_for_slice', type='BOOLEAN')
        inflated_object.modifiers['mask_for_slice'].object = bpy.data.objects['masking_cube']
        inflated_object.modifiers['mask_for_slice'].operation = 'DIFFERENCE'
        inflated_object.modifiers['mask_for_slice'].double_threshold = 0
    bpy.context.scene.objects.active = cur_plane_obj
    if cur_plane_obj.modifiers.get('Boolean') is None:
        cur_plane_obj.modifiers.new('Boolean', type='BOOLEAN')
        cur_plane_obj.modifiers['Boolean'].object = bpy.data.objects['joint_brain']
        cur_plane_obj.modifiers['Boolean'].operation = 'INTERSECT'
    cur_plane_obj.hide_select = True


def clear_slice():
    optional_cut_types = ['sagital', 'coronal', 'axial']
    bpy.data.objects['masking_cube'].location = (20, 20, 20)
    bpy.context.scene.is_sliced_ind = -1
    for cut_type in optional_cut_types:
        if bpy.data.objects.get('{}_plane'.format(cut_type)):
            bpy.data.objects['{}_plane'.format(cut_type)].hide = True
            bpy.data.objects['{}_plane'.format(cut_type)].hide_render = True
    return True


def create_joint_brain_obj():
    if bpy.data.objects.get('joint_brain') is None:
        bpy.ops.mesh.primitive_cube_add(radius=0.1, location=(500, 500, 500))
        bpy.context.object.name = 'joint_brain'
        for hemi in ['lh', 'rh', 'Brain-Stem', 'Left-Cerebellum-Cortex', 'Right-Cerebellum-Cortex']:
            if hemi not in bpy.data.objects:
                continue
            bpy.ops.object.modifier_add(type='BOOLEAN')
            bpy.data.objects['joint_brain'].modifiers['Boolean'].object = bpy.data.objects[hemi]
            bpy.data.objects['joint_brain'].modifiers['Boolean'].operation = 'UNION'
            bpy.context.scene.objects.active = bpy.data.objects['joint_brain']
            bpy.ops.object.modifier_apply(modifier='Boolean')
        bpy.data.objects['joint_brain'].hide = True
        bpy.data.objects['joint_brain'].hide_render = True

# def get_cm():
#     return ColorbarPanel.cm
#
#
# def colorbar_values_are_locked():
#     return bpy.context.scene.lock_min_max
#
#
# def lock_colorbar_values(val=True):
#     bpy.context.scene.lock_min_max = val
#
#
# def load_colormap():
#     colormap_fname = op.join(mu.file_fol(), 'color_maps', '{}.npy'.format(
#         bpy.context.scene.colorbar_files.replace('-', '_')))
#     colormap = np.load(colormap_fname)
#     ColorbarPanel.cm = colormap
#     for ind in range(colormap.shape[0]):
#         cb_obj_name = 'cb.{0:0>3}'.format(ind)
#         cb_obj = bpy.data.objects[cb_obj_name]
#         cur_mat = cb_obj.active_material
#         cur_mat.diffuse_color = colormap[ind]
#         # print('Changing {} to {}'.format(cb_obj_name, colormap[ind]))
#
#
# def get_colormap_name():
#     return bpy.context.scene.colorbar_files
#
#
# @mu.tryit()
# def set_colorbar_title(val):
#     val = val.lstrip()
#     val = '     {}'.format(val)
#     init = ColorbarPanel.init
#     bpy.data.objects['colorbar_title'].data.body = bpy.data.objects['colorbar_title_camera'].data.body = val
#     ColorbarPanel.init = False
#     bpy.context.scene.colorbar_title = val
#     ColorbarPanel.init = init
#
#
# def get_colorbar_title():
#     return bpy.context.scene.colorbar_title
#
#
# def set_colorbar_max_min(max_val, min_val, force_update=False):
#     if max_val >= min_val:
#         init = ColorbarPanel.init
#         if force_update:
#             ColorbarPanel.init = True
#         bpy.context.scene.colorbar_max = max_val
#         bpy.context.scene.colorbar_min = min_val
#         # mu.set_graph_att('colorbar_max', max_val)
#         # mu.set_graph_att('colorbar_min', min_val)
#         # _addon().s.colorbar_max = max_val
#         # _addon().s.colorbar_min = min_val
#         ColorbarPanel.init = init
#     else:
#         print('set_colorbar_max_min: ax_val < min_val!')
#
#
# def get_colorbar_max_min():
#     return bpy.context.scene.colorbar_max, bpy.context.scene.colorbar_min
#
#
# def set_colorbar_max(val, prec=None, check_minmax=True):
#     if not check_minmax or bpy.context.scene.colorbar_max > bpy.context.scene.colorbar_min:
#         _set_colorbar_min_max('max', val, prec)
#     else:
#         prev_max = float(bpy.data.objects['colorbar_max'].data.body)
#         ColorbarPanel.init = False
#         bpy.context.scene.colorbar_max = prev_max
#         ColorbarPanel.init = True
#
#
# def get_colorbar_max():
#     return bpy.context.scene.colorbar_max
#
#
# def set_colorbar_min(val, prec=None, check_minmax=True):
#     if not check_minmax or bpy.context.scene.colorbar_max > bpy.context.scene.colorbar_min:
#         _set_colorbar_min_max('min', val, prec)
#     else:
#         prev_min = float(bpy.data.objects['colorbar_min'].data.body)
#         ColorbarPanel.init = False
#         bpy.context.scene.colorbar_min = prev_min
#         ColorbarPanel.init = True
#
#
# def get_colorbar_min():
#     return bpy.context.scene.colorbar_min
#
#
# def get_colorbar_prec():
#     return bpy.context.scene.colorbar_prec
#
#
# def set_colorbar_prec(val):
#     bpy.context.scene.colorbar_prec = val
#
#
# def _set_colorbar_min_max(field, val, prec):
#     if prec is None or prec not in PERC_FORMATS:
#         prec = bpy.context.scene.colorbar_prec
#         if prec not in PERC_FORMATS:
#             print('Wrong value for prec, should be in {}'.format(PERC_FORMATS.keys()))
#     prec_str = PERC_FORMATS[prec]
#     cb_obj = bpy.data.objects.get('colorbar_{}'.format(field))
#     cb_camera_obj = bpy.data.objects.get('colorbar_{}_camera'.format(field))
#     if not cb_obj is None and not cb_camera_obj is None:
#         cb_obj.data.body = cb_camera_obj.data.body = prec_str.format(val)
#     else:
#         print('_set_colorbar_min_max: field error ({})! must be max / min!'.format(field))
#
#
# def set_colormap(colormap_name):
#     if colormap_name in ColorbarPanel.maps_names:
#         bpy.context.scene.colorbar_files = colormap_name
#     else:
#         print('No such colormap! {}'.format(colormap_name))
#
#
# def hide_cb_center_update(self, context):
#     hide_center(bpy.context.scene.hide_cb_center)
#
#
# def hide_center(do_hide):
#     n = len(bpy.data.objects['cCB'].children)
#     for cb in bpy.data.objects['cCB'].children:
#         if not do_hide:
#             cb.hide = False
#         num = int(cb.name.split('.')[-1])
#         if do_hide and n / 2 - 10 < num < n / 2 + 10:
#             cb.hide = True
#
#
# def colormap_update(self, context):
#     if ColorbarPanel.init:
#         load_colormap()
#
#
# def colorbar_update(self, context):
#     if ColorbarPanel.init:
#         ColorbarPanel.colorbar_updated = True
#         set_colorbar_title(bpy.context.scene.colorbar_title)
#         set_colorbar_max(bpy.context.scene.colorbar_max)
#         set_colorbar_min(bpy.context.scene.colorbar_min)
#
#
# def show_cb_in_render_update(self, context):
#     show_cb_in_render(bpy.context.scene.show_cb_in_render)
#
#
# def show_cb_in_render(val=True):
#     mu.show_hide_hierarchy(val, 'colorbar_camera', True, False)
#     mu.show_hide_hierarchy(val, 'cCB_camera', True, False)
#
#
# def colorbar_y_update(self, context):
#     bpy.data.objects['cCB'].location[0] = -bpy.context.scene.colorbar_y
#
#
# def colorbar_text_y_update(self, context):
#     bpy.data.objects['colorbar_max'].location[0] = -bpy.context.scene.colorbar_text_y
#     bpy.data.objects['colorbar_min'].location[0] = -bpy.context.scene.colorbar_text_y
#     bpy.data.objects['colorbar_title'].location[0] = -bpy.context.scene.colorbar_text_y
#
#
# def colorbar_draw(self, context):
#     layout = self.layout
#     layout.prop(context.scene, "colorbar_files", text="")
#     layout.prop(context.scene, "colorbar_title", text="Title:")
#     row = layout.row(align=0)
#     row.prop(context.scene, "colorbar_min", text="min:")
#     row.prop(context.scene, "colorbar_max", text="max:")
#     layout.prop(context.scene, 'hide_cb_center', text='Hide center')
#     layout.prop(context.scene, 'colorbar_prec', text='precision')
#     layout.prop(context.scene, 'lock_min_max', text='Lock values')
#     layout.prop(context.scene, 'show_cb_in_render', text='Show in rendering')
#     layout.prop(context.scene, 'update_cb_location', text='Update location')
#     if bpy.context.scene.update_cb_location:
#         layout.prop(context.scene, "colorbar_y", text="y axis")
#         layout.prop(context.scene, "colorbar_text_y", text="text y axis")
#     # layout.operator(ColorbarButton.bl_idname, text="Do something", icon='ROTATE')


def show_full_slice_update(self, context):
    for cut_type in ['axial', 'coronal', 'sagital']:
        if bpy.data.objects.get('{}_plane'.format(cut_type)):
            bpy.data.objects['{}_plane'.format(cut_type)].modifiers['Boolean'].show_viewport =\
                not bpy.context.scene.show_full_slice


class SliceBrainButton(bpy.types.Operator):
    bl_idname = "mmvt.slice_brain_button"
    bl_label = "Slice Brain button"
    bl_options = {"UNDO"}

    def invoke(self, context, event=None):
        slice_brain()
        return {'FINISHED'}


class SliceBrainClearButton(bpy.types.Operator):
    bl_idname = "mmvt.slice_brain_clear_button"
    bl_label = "Slice Brain Clear button"
    bl_options = {"UNDO"}

    def invoke(self, context, event=None):
        clear_slice()
        return {'FINISHED'}


items_names = [("axial", "Axial"), ("coronal", "Coronal"), ("sagital", 'Sagital')]
items = [(n[0], n[1], '', ind) for ind, n in enumerate(items_names)]
bpy.types.Scene.slicer_cut_type = bpy.props.EnumProperty(items=items, description='Type of slice')
# bpy.types.Scene.slice_using_left_click = bpy.props.BoolProperty(
#     default=True, description="slice_using_left_click", update=show_cb_in_render_update)
bpy.types.Scene.show_full_slice = bpy.props.BoolProperty(default=False, update=show_full_slice_update)
# bpy.types.Scene.show_full_slice = bpy.props.BoolProperty()


def slicer_draw(self, context):
    layout = self.layout
    layout.prop(context.scene, "slicer_cut_type", text="")
    layout.operator(SliceBrainButton.bl_idname, text="Slice brain", icon='FACESEL_HLT')
    layout.operator(SliceBrainClearButton.bl_idname, text="Clear slice", icon='MESH_CUBE')
    layout.prop(context.scene, 'show_full_slice', text='Show full slice')


class SlicerPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Slicer"
    addon = None
    init = False

    def draw(self, context):
        if SlicerPanel.init:
            slicer_draw(self, context)


def init(addon):
    SlicerPanel.addon = addon
    bpy.context.scene.show_full_slice = False
    create_joint_brain_obj()
    # print('init slicer')
    # bpy.context.scene.is_sliced_ind = -1
    # bpy.context.scene.last_cursor_location = [0.0, 0.0, 0.0]
    bpy.types.Scene.last_cursor_location = bpy.props.FloatVectorProperty(default=(0.0, 0.0, 0.0),size=3)
    bpy.types.Scene.is_sliced_ind = bpy.props.IntProperty(default=-1)
    bpy.context.scene.last_cursor_location = (0.0, 0.0, 0.0)
    bpy.context.scene.is_sliced_ind = -1
    SlicerPanel.init = True
    register()


def register():
    try:
        unregister()
        bpy.utils.register_class(SlicerPanel)
        bpy.utils.register_class(SliceBrainButton)
        bpy.utils.register_class(SliceBrainClearButton)
        # print('SlicerPanel was registered')
        # print('SliceBrainButton was registered')
        # print('SliceBrainClearButton was registered')
    except:
        print("Can't register Slicer Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(SlicerPanel)
        bpy.utils.unregister_class(SliceBrainButton)
        bpy.utils.unregister_class(SliceBrainClearButton)
    except:
        pass
