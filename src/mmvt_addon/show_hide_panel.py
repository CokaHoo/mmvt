import bpy
import mmvt_utils as mu
import mathutils
import glob
import os.path as op
import re


def _addon():
    return ShowHideObjectsPanel.addon


def zoom(delta):
    c = mu.get_view3d_context()
    bpy.ops.view3d.zoom(c, delta=delta)


def view_all():
    c = mu.get_view3d_context()
    bpy.ops.view3d.view_all(c)


def rotate_brain(dx=None, dy=None, dz=None, keep_rotating=False, save_image=False):
    dx = bpy.context.scene.rotate_dx if dx is None else dx
    dy = bpy.context.scene.rotate_dy if dy is None else dy
    dz = bpy.context.scene.rotate_dz if dz is None else dz
    bpy.context.scene.rotate_dx, bpy.context.scene.rotate_dy, bpy.context.scene.rotate_dz = dx, dy, dz
    rv3d = mu.get_view3d_region()
    rv3d.view_rotation.rotate(mathutils.Euler((dx, dy, dz)))
    if bpy.context.scene.rotate_and_render or save_image:
        _addon().save_image('rotation', view_selected=bpy.context.scene.save_selected_view)
    if keep_rotating:
        start_rotating()


def view_all():
    c = mu.get_view3d_context()
    bpy.ops.view3d.view_all(c)


def start_rotating():
    bpy.context.scene.rotate_brain = True


def stop_rotating():
    bpy.context.scene.rotate_brain = False


def show_only_redner_update(self, context):
    mu.show_only_render(bpy.context.scene.show_only_render)


def show_hide_hierarchy(do_hide, obj_name):
    if bpy.data.objects.get(obj_name) is not None:
        obj = bpy.data.objects[obj_name]
        hide_obj(obj, do_hide)
        # bpy.data.objects[obj].hide = do_hide
        for child in obj.children:
            hide_obj(child, do_hide)


def show_hide_hemi(val, hemi):
    # show_hide_hierarchy(val, 'Cortex-{}'.format(hemi))
    show_hide_hierarchy(val, 'Cortex-inflated-{}'.format(hemi))
    # for obj_name in [hemi, 'inflated_{}'.format(hemi)]:
    obj_name = 'inflated_{}'.format(hemi)
    if bpy.data.objects.get(obj_name) is not None:
        hide_obj(bpy.data.objects[obj_name], val)


def show_hemis():
    for obj_name in ['rh', 'lh', 'Cortex-inflated-rh', 'Cortex-inflated-lh']:
        show_hide_hierarchy(False, obj_name)


def hide_obj(obj, val=True):
    obj.hide = val
    obj.hide_render = val


def show_hide_sub_cortical_update(self, context):
    show_hide_sub_corticals(bpy.context.scene.objects_show_hide_sub_cortical)


def hide_subcorticals():
    show_hide_sub_corticals(True)


def show_subcorticals():
    show_hide_sub_corticals(False)


def show_hide_sub_corticals(do_hide=True):
    show_hide_hierarchy(do_hide, "Subcortical_structures")
    # show_hide_hierarchy(bpy.context.scene.objects_show_hide_sub_cortical, "Subcortical_activity_map")
    # We split the activity map into two types: meg for the same activation for the each structure, and fmri
    # for a better resolution, like on the cortex.
    if not do_hide:
        fmri_show = bpy.context.scene.subcortical_layer == 'fmri'
        meg_show = bpy.context.scene.subcortical_layer == 'meg'
        show_hide_hierarchy(not fmri_show, "Subcortical_fmri_activity_map")
        show_hide_hierarchy(not meg_show, "Subcortical_meg_activity_map")
    else:
        show_hide_hierarchy(True, "Subcortical_fmri_activity_map")
        show_hide_hierarchy(True, "Subcortical_meg_activity_map")


# def flip_camera_ortho_view():
#     options = ['ORTHO', 'CAMERA']
#     bpy.types.Scene.in_camera_view = not bpy.types.Scene.in_camera_view
#     bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_perspective = options[
#         int(bpy.types.Scene.in_camera_view)]


def show_sagital():
    if bpy.types.Scene.in_camera_view and bpy.data.objects.get("Camera_empty") is not None:
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'saggital':
            bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, 1.5707963705062866]
            bpy.types.Scene.current_view = 'saggital'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, 1.5707963705062866]
            else:
                # print('in ShowSaggital else')
                bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, -1.5707963705062866]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction
            # bpy.types.Scene.time_of_view_selection = mu.get_time_obj()
    else:
        bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_perspective = 'ORTHO'
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'saggital':
            bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0.5, 0.5, -0.5, -0.5]
            bpy.types.Scene.current_view = 'saggital'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0.5, 0.5, -0.5, -0.5]
            else:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0.5, 0.5, 0.5, 0.5]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction

    # view_all()
    # zoom(-1)
    bpy.types.Scene.time_of_view_selection = mu.get_time_obj()


def show_coronal(show_frontal=False):
    if show_frontal:
        bpy.types.Scene.current_view = 'coronal'
        bpy.types.Scene.current_view_direction = 0
        return

    if bpy.types.Scene.in_camera_view and bpy.data.objects.get("Camera_empty") is not None:
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'coronal':
            bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, 3.1415927410125732]
            bpy.types.Scene.current_view = 'coronal'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, 3.1415927410125732]
            else:
                # print('in ShowCoronal else')
                bpy.data.objects["Camera_empty"].rotation_euler = [0.0, 0.0, 0.0]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction
        bpy.types.Scene.time_of_view_selection = mu.get_time_obj()
    else:
        bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_perspective = 'ORTHO'
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'coronal':
            bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0.7071068286895752,
                                                                                    0.7071068286895752, -0.0, -0.0]
            bpy.types.Scene.current_view = 'coronal'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0.7071068286895752,
                                                                                        0.7071068286895752, -0.0, -0.0]
            else:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0, 0, 0.7071068286895752,
                                                                                        0.7071068286895752]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction
        bpy.types.Scene.time_of_view_selection = mu.get_time_obj()
        # print(bpy.ops.view3d.viewnumpad())
    # view_all()
    # zoom(-1)


def show_axial():
    if bpy.types.Scene.in_camera_view and bpy.data.objects.get("Camera_empty") is not None:
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'axial':
            bpy.data.objects["Camera_empty"].rotation_euler = [1.5707963705062866, 0.0, 3.1415927410125732]
            bpy.types.Scene.current_view = 'axial'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.objects["Camera_empty"].rotation_euler = [1.5707963705062866, 0.0, 3.1415927410125732]
            else:
                # print('in ShowAxial else')
                bpy.data.objects["Camera_empty"].rotation_euler = [-1.5707963705062866, 0.0, 3.1415927410125732]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction
        bpy.types.Scene.time_of_view_selection = mu.get_time_obj()
    else:
        bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_perspective = 'ORTHO'
        if mu.get_time_from_event(mu.get_time_obj()) > 2 or bpy.types.Scene.current_view != 'axial':
            bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [1, 0, 0, 0]
            bpy.types.Scene.current_view = 'axial'
            bpy.types.Scene.current_view_direction = 0
        else:
            if bpy.types.Scene.current_view_direction == 1:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [1, 0, 0, 0]
            else:
                bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d.view_rotation = [0, 1, 0, 0]
            bpy.types.Scene.current_view_direction = not bpy.types.Scene.current_view_direction
        bpy.types.Scene.time_of_view_selection = mu.get_time_obj()
    # view_all()
    # zoom(-1)


def _split_view():
    ShowHideObjectsPanel.split_view += 1
    if ShowHideObjectsPanel.split_view == 3:
        ShowHideObjectsPanel.split_view = 0
    split_view(ShowHideObjectsPanel.split_view)


@mu.tryit()
def split_view(view):
    import math
    if not ShowHideObjectsPanel.init:
        return
    if view != 0:
        _addon().hide_subcorticals()
    pial_shift = 10
    inflated_shift = 13
    if view == 0: # Normal
        show_coronal()
        if _addon().is_inflated():
            bpy.data.objects['inflated_lh'].location[0] = 0
            bpy.data.objects['inflated_lh'].rotation_euler[2] = 0
            bpy.data.objects['inflated_rh'].location[0] = 0
            bpy.data.objects['inflated_rh'].rotation_euler[2] = 0
        else:
            bpy.data.objects['lh'].location[0] = 0
            bpy.data.objects['lh'].rotation_euler[2] = 0
            bpy.data.objects['rh'].location[0] = 0
            bpy.data.objects['rh'].rotation_euler[2] = 0
    elif view == 1: # Split lateral
        show_coronal()
        # lateral split view
        # inflated_lh: loc  x:13, rot z: -90
        # inflated_lr: loc  x:-13, rot z: 90
        if _addon().is_inflated():
            bpy.data.objects['inflated_lh'].location[0] = inflated_shift
            bpy.data.objects['inflated_lh'].rotation_euler[2] = -math.pi / 2
            bpy.data.objects['inflated_rh'].location[0] = -inflated_shift
            bpy.data.objects['inflated_rh'].rotation_euler[2] = math.pi / 2
        else:
            bpy.data.objects['lh'].location[0] = pial_shift
            bpy.data.objects['lh'].rotation_euler[2] = -math.pi / 2
            bpy.data.objects['rh'].location[0] = -pial_shift
            bpy.data.objects['rh'].rotation_euler[2] = math.pi / 2
    elif view == 2:
        # medial split medial
        # inflated_lh: loc  x:13, rot z: 90
        # inflated_lr: loc  x:-13, rot z: -90
        if _addon().is_inflated():
            bpy.data.objects['inflated_lh'].location[0] = inflated_shift
            bpy.data.objects['inflated_lh'].rotation_euler[2] = math.pi / 2
            bpy.data.objects['inflated_rh'].location[0] = -inflated_shift
            bpy.data.objects['inflated_rh'].rotation_euler[2] = -math.pi / 2
        else:
            bpy.data.objects['lh'].location[0] = pial_shift - 2
            bpy.data.objects['lh'].rotation_euler[2] = math.pi / 2
            bpy.data.objects['rh'].location[0] = -(pial_shift - 2)
            bpy.data.objects['rh'].rotation_euler[2] = -math.pi / 2


def maximize_brain():
    context = mu.get_view3d_context()
    bpy.ops.screen.screen_full_area(context)


def minimize_brain():
    context = mu.get_view3d_context()
    bpy.ops.screen.back_to_previous(context)


class ShowSaggital(bpy.types.Operator):
    bl_idname = "mmvt.show_saggital"
    bl_label = "mmvt show_saggital"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        show_sagital()
        return {"FINISHED"}


class ShowCoronal(bpy.types.Operator):
    bl_idname = "mmvt.show_coronal"
    bl_label = "mmvt show_coronal"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        show_coronal()
        return {"FINISHED"}


class MaxMinBrain(bpy.types.Operator):
    bl_idname = "mmvt.max_min_brain"
    bl_label = "mmvt max_min_brain"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        if bpy.context.scene.brain_max_min:
            maximize_brain()
        else:
            minimize_brain()
        bpy.context.scene.brain_max_min = not bpy.context.scene.brain_max_min
        return {"FINISHED"}


class SplitView(bpy.types.Operator):
    bl_idname = "mmvt.split_view"
    bl_label = "mmvt split view"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        _split_view()
        return {"FINISHED"}


class ShowAxial(bpy.types.Operator):
    bl_idname = "mmvt.show_axial"
    bl_label = "mmvt show_axial"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        show_axial()
        return {"FINISHED"}




# class FlipCameraView(bpy.types.Operator):
#     bl_idname = "mmvt.flip_camera_view"
#     bl_label = "mmvt flip camera view"
#     bl_options = {"UNDO"}
#
#     @staticmethod
#     def invoke(self, context, event=None):
#         flip_camera_ortho_view()
#         return {"FINISHED"}


class ShowHideLH(bpy.types.Operator):
    bl_idname = "mmvt.show_hide_lh"
    bl_label = "mmvt show_hide_lh"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.objects_show_hide_lh = not bpy.context.scene.objects_show_hide_lh
        show_hide_hemi(bpy.context.scene.objects_show_hide_lh, 'lh')
        return {"FINISHED"}


class ShowHideRH(bpy.types.Operator):
    bl_idname = "mmvt.show_hide_rh"
    bl_label = "mmvt show_hide_rh"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.objects_show_hide_rh = not bpy.context.scene.objects_show_hide_rh
        show_hide_hemi(bpy.context.scene.objects_show_hide_rh, 'rh')
        return {"FINISHED"}


class ShowHideSubCorticals(bpy.types.Operator):
    bl_idname = "mmvt.show_hide_sub"
    bl_label = "mmvt show_hide_sub"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.objects_show_hide_sub_cortical = not bpy.context.scene.objects_show_hide_sub_cortical
        show_hide_sub_corticals(bpy.context.scene.objects_show_hide_sub_cortical)
        return {"FINISHED"}


class ShowHideSubCerebellum(bpy.types.Operator):
    bl_idname = "mmvt.show_hide_cerebellum"
    bl_label = "mmvt show_hide_cerebellum"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        bpy.context.scene.objects_show_hide_cerebellum = not bpy.context.scene.objects_show_hide_cerebellum
        show_hide_hierarchy(bpy.context.scene.objects_show_hide_cerebellum, 'Cerebellum')
        show_hide_hierarchy(bpy.context.scene.objects_show_hide_cerebellum, 'Cerebellum_fmri_activity_map')
        show_hide_hierarchy(bpy.context.scene.objects_show_hide_cerebellum, 'Cerebellum_meg_activity_map')
        return {"FINISHED"}


class ShowHideObjectsPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Show Hide Brain"
    addon = None
    init = False
    split_view = 0
    split_view_text = {0:'Split Lateral', 1:'Split Medial', 2:'Normal view'}

    def draw(self, context):
        if not ShowHideObjectsPanel.init:
            return
        layout = self.layout
        vis = dict(Right = not bpy.context.scene.objects_show_hide_rh, Left = not bpy.context.scene.objects_show_hide_lh)
        show_hide_icon = dict(show='RESTRICT_VIEW_OFF', hide='RESTRICT_VIEW_ON')
        row = layout.row(align=True)
        for hemi in ['Left', 'Right']:
            action = 'show' if vis[hemi] else 'hide'
            show_text = '{} {}'.format('Hide' if vis[hemi] else 'Show', hemi)
            show_icon = show_hide_icon[action]
            bl_idname = ShowHideLH.bl_idname if hemi == 'Left' else ShowHideRH.bl_idname
            row.operator(bl_idname, text=show_text, icon=show_icon)
        subs_exist = bpy.data.objects.get('Subcortical_structures', None) is not None and \
                     len(bpy.data.objects['Subcortical_structures'].children) > 0
        if _addon().is_pial() and subs_exist:
            sub_vis = not bpy.context.scene.objects_show_hide_sub_cortical
            sub_show_text = '{} Subcortical'.format('Hide' if sub_vis else 'Show')
            sub_icon = show_hide_icon['show' if sub_vis else 'hide']
            layout.operator(ShowHideSubCorticals.bl_idname, text=sub_show_text, icon=sub_icon)
        # if bpy.data.objects.get('Cerebellum'):
        #     sub_vis = not bpy.context.scene.objects_show_hide_cerebellum
        #     sub_show_text = '{} Cerebellum'.format('Hide' if sub_vis else 'Show')
        #     sub_icon = show_hide_icon['show' if sub_vis else 'hide']
        #     layout.operator(ShowHideSubCerebellum.bl_idname, text=sub_show_text, icon=sub_icon)
        row = layout.row(align=True)
        row.operator(ShowAxial.bl_idname, text='Axial', icon='AXIS_TOP')
        row.operator(ShowCoronal.bl_idname, text='Coronal', icon='AXIS_FRONT')
        row.operator(ShowSaggital.bl_idname, text='Saggital', icon='AXIS_SIDE')
        layout.operator(SplitView.bl_idname, text=self.split_view_text[self.split_view], icon='ALIGN')
        # layout.operator(MaxMinBrain.bl_idname,
        #                 text="{} Brain".format('Maximize' if bpy.context.scene.brain_max_min else 'Minimize'),
        #                 icon='TRIA_UP' if bpy.context.scene.brain_max_min else 'TRIA_DOWN')
        layout.prop(context.scene, 'rotate_brain')
        layout.prop(context.scene, 'rotate_and_render')
        row = layout.row(align=True)
        row.prop(context.scene, 'rotate_dx')
        row.prop(context.scene, 'rotate_dy')
        row.prop(context.scene, 'rotate_dz')
        # views_options = ['Camera', 'Ortho']
        # next_view = views_options[int(bpy.context.scene.in_camera_view)]
        # icons = ['SCENE', 'MANIPUL']
        # next_icon = icons[int(bpy.context.scene.in_camera_view)]
        # row = layout.row(align=True)
        # layout.operator(FlipCameraView.bl_idname, text='Change to {} view'.format(next_view), icon=next_icon)
        layout.prop(context.scene, 'show_only_render', text="Show only rendered objects")



bpy.types.Scene.objects_show_hide_lh = bpy.props.BoolProperty(
    default=True, description="Show left hemisphere")#,update=show_hide_lh)
bpy.types.Scene.objects_show_hide_rh = bpy.props.BoolProperty(
    default=True, description="Show right hemisphere")#, update=show_hide_rh)
bpy.types.Scene.objects_show_hide_sub_cortical = bpy.props.BoolProperty(
    default=True, description="Show sub cortical")#, update=show_hide_sub_cortical_update)
bpy.types.Scene.objects_show_hide_cerebellum = bpy.props.BoolProperty(
    default=True, description="Show Cerebellum")
bpy.types.Scene.show_only_render = bpy.props.BoolProperty(
    default=True, description="Show only rendered objects", update=show_only_redner_update)
bpy.types.Scene.rotate_brain = bpy.props.BoolProperty(default=False, name='Rotate the brain')
bpy.types.Scene.rotate_and_render = bpy.props.BoolProperty(default=False, name='Save an image each rotation')
bpy.types.Scene.brain_max_min = bpy.props.BoolProperty()

bpy.types.Scene.rotate_dx = bpy.props.FloatProperty(default=0.1, min=-0.1, max=0.1, name='x')
bpy.types.Scene.rotate_dy = bpy.props.FloatProperty(default=0.1, min=-0.1, max=0.1, name='y')
bpy.types.Scene.rotate_dz = bpy.props.FloatProperty(default=0.1, min=-0.1, max=0.1, name='z')

bpy.types.Scene.current_view = 'free'
bpy.types.Scene.time_of_view_selection = mu.get_time_obj
bpy.types.Scene.current_view_direction = 0
# bpy.types.Scene.in_camera_view = 0


def init(addon):
    ShowHideObjectsPanel.addon = addon
    if bpy.data.objects.get('lh', None) is None:
        print('No brain!')
        return
    bpy.context.scene.objects_show_hide_rh = False
    bpy.context.scene.objects_show_hide_lh = False
    bpy.context.scene.objects_show_hide_sub_cortical = False
    show_hide_sub_corticals(False)
    show_hemis()
    bpy.context.scene.show_only_render = False
    bpy.context.scene.brain_max_min = True
    for fol in ['Cerebellum', 'Cerebellum_fmri_activity_map', 'Cerebellum_meg_activity_map']:
        show_hide_hierarchy(True, fol)
    bpy.context.scene.rotate_brain = False
    bpy.context.scene.rotate_and_render = False
    bpy.context.scene.rotate_dz = 0.02
    bpy.context.scene.rotate_dx = 0.00
    bpy.context.scene.rotate_dy = 0.00
    # show_hide_hemi(False, 'rh')
    # show_hide_hemi(False, 'lh')
    # hide_obj(bpy.data.objects[obj_func_name], val)
    # view_all()
    # zoom(-1)

    register()
    ShowHideObjectsPanel.init = True


def register():
    try:
        unregister()
        bpy.utils.register_class(ShowHideObjectsPanel)
        bpy.utils.register_class(ShowHideLH)
        bpy.utils.register_class(ShowHideRH)
        bpy.utils.register_class(ShowSaggital)
        bpy.utils.register_class(ShowCoronal)
        bpy.utils.register_class(ShowAxial)
        bpy.utils.register_class(SplitView)
        bpy.utils.register_class(MaxMinBrain)
        # bpy.utils.register_class(FlipCameraView)
        bpy.utils.register_class(ShowHideSubCorticals)
        bpy.utils.register_class(ShowHideSubCerebellum)
        # print('Show Hide Panel was registered!')
    except:
        print("Can't register Show Hide Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(ShowHideObjectsPanel)
        bpy.utils.unregister_class(ShowHideLH)
        bpy.utils.unregister_class(ShowHideRH)
        bpy.utils.unregister_class(ShowSaggital)
        bpy.utils.unregister_class(ShowCoronal)
        bpy.utils.unregister_class(ShowAxial)
        bpy.utils.unregister_class(SplitView)
        bpy.utils.unregister_class(MaxMinBrain)
        # bpy.utils.unregister_class(FlipCameraView)
        bpy.utils.unregister_class(ShowHideSubCorticals)
        bpy.utils.unregister_class(ShowHideSubCerebellum)
    except:
        pass
        # print("Can't unregister Freeview Panel!")
