import mmvt_utils as mu
import colors_utils as cu
import numpy as np
import os.path as op
import time
import itertools
from collections import defaultdict, OrderedDict
import glob
import traceback
from functools import partial

try:
    import bpy
    import bpy_extras
except:
    bpy = mu.empty_bpy
    bpy_extras = mu.empty_bpy_extras

try:
    import mne
    MNE_EXIST = True
except:
    MNE_EXIST = False

HEMIS = mu.HEMIS
(WIC_MEG, WIC_MEG_LABELS, WIC_FMRI, WIC_FMRI_DYNAMICS, WIC_FMRI_LABELS, WIC_FMRI_CLUSTERS, WIC_EEG, WIC_MEG_SENSORS,
WIC_ELECTRODES, WIC_ELECTRODES_DISTS, WIC_ELECTRODES_SOURCES, WIC_ELECTRODES_STIM, WIC_MANUALLY, WIC_GROUPS, WIC_VOLUMES,
 WIC_CONN_LABELS_AVG) = range(16)


def _addon():
    return ColoringMakerPanel.addon


def plot_meg(t=-1, save_image=False, view_selected=False):
    if t != -1:
        bpy.context.scene.frame_current = t
    activity_map_coloring('MEG')
    if save_image:
        return _addon().save_image('meg', view_selected, t)
    else:
        return True


# @mu.dump_args
def plot_stc(stc, t, threshold=0,  save_image=True, view_selected=False, subject='', n_jobs=-1):
    import mne
    subject = mu.get_user() if subject == '' else subject
    n_jobs = mu.get_n_jobs(n_jobs)

    def create_stc_t(stc, t):
        C = max([stc.rh_data.shape[0], stc.lh_data.shape[0]])
        stc_lh_data = stc.lh_data[:, t:t + 1] if stc.lh_data.shape[0] > 0 else np.zeros((C, 1))
        stc_rh_data = stc.rh_data[:, t:t + 1] if stc.rh_data.shape[0] > 0 else np.zeros((C, 1))
        data = np.concatenate([stc_lh_data, stc_rh_data])
        vertno = max([len(stc.lh_vertno), len(stc.rh_vertno)])
        lh_vertno = stc.lh_vertno if len(stc.lh_vertno) > 0 else np.arange(0, vertno)
        rh_vertno = stc.rh_vertno if len(stc.rh_vertno) > 0 else np.arange(0, vertno) + max(lh_vertno) + 1
        vertices = [lh_vertno, rh_vertno]
        stc_t = mne.SourceEstimate(data, vertices, stc.tmin + t * stc.tstep, stc.tstep, subject=subject)
        return stc_t

    # subjects_dir = mu.get_link_dir(mu.get_links_dir(), 'subjects')
    subjects_dir = mu.get_parent_fol(mu.get_user_fol())
    if subjects_dir:
        print('subjects_dir: {}'.format(subjects_dir))
    stc_t = create_stc_t(stc, t)
    vertices_to = mne.grade_to_vertices(subject, None, subjects_dir=subjects_dir)
    stc_t_smooth = mne.morph_data(subject, subject, stc_t, n_jobs=n_jobs, grade=vertices_to, subjects_dir=subjects_dir)

    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
    else:
        data_min, data_max = ColoringMakerPanel.meg_data_min, ColoringMakerPanel.meg_data_max
        _addon().set_colorbar_max_min(data_max, data_min)
        # _addon().set_colorbar_prec(abs(int(np.round(np.log10(data_max)))))
    normalize_data = True
    # if normalize_data:
    #     stc_t_smooth.rh_data /= data_max
    #     stc_t_smooth.lh_data /= data_max
    #     data_min, data_max = 0, 1
    colors_ratio = 256 / (data_max - data_min)
    set_default_colormap(data_min, data_max)
    fname = plot_stc_t(stc_t_smooth.rh_data, stc_t_smooth.lh_data, t, data_min, colors_ratio, threshold, save_image, view_selected)
    return fname, stc_t_smooth


def set_default_colormap(data_min, data_max):
    # todo: should read default values from ini file
    if not (data_min == 0 and data_max == 0) and not _addon().colorbar_values_are_locked():
        if data_min == 0 or np.sign(data_min) == np.sign(data_max):
            _addon().set_colormap('YlOrRd')
        else:
            _addon().set_colormap('BuPu-YlOrRd')


def plot_stc_t(rh_data, lh_data, t, data_min=None, colors_ratio=None, threshold=0, save_image=False, view_selected=False):
    if data_min is None or colors_ratio is None:
        data_min = min([np.min(rh_data), np.min(lh_data)])
        data_max = max([np.max(rh_data), np.max(lh_data)])
        colors_ratio = 256 / (data_max - data_min)
    for hemi in mu.HEMIS:
        data = rh_data if hemi == 'rh' else lh_data
        color_hemi_data(hemi, data, data_min, colors_ratio, threshold)
    if save_image:
        return _addon().save_image('stc', view_selected, t)
    else:
        return True


def set_threshold(val):
    bpy.context.scene.coloring_threshold = val


def can_color_obj(obj):
    cur_mat = obj.active_material
    return 'RGB' in cur_mat.node_tree.nodes


def contours_coloring_update(self, context):
    user_fol = mu.get_user_fol()
    d = {}
    items = [('all labels', 'all labels', '', 0)]
    for hemi in mu.HEMIS:
        d[hemi] = np.load(op.join(user_fol, '{}_contours_{}.npz'.format(
            bpy.context.scene.contours_coloring, hemi)))
        ColoringMakerPanel.labels[hemi] = d[hemi]['labels']
        items.extend([(c, c, '', ind + 1) for ind, c in enumerate(d[hemi]['labels'])])
    bpy.types.Scene.labels_contures = bpy.props.EnumProperty(items=items, update=labels_contures_update)
    bpy.context.scene.labels_contures = 'all labels' #d[hemi]['labels'][0]
    ColoringMakerPanel.labels_contures = d


def labels_contures_update(self, context):
    if not ColoringMakerPanel.init:
        return
    if bpy.context.scene.labels_contures == 'all labels':
        color_contours()
    else:
        hemi = 'rh' if bpy.context.scene.labels_contures in ColoringMakerPanel.labels['rh'] else 'lh'
        color_contours(bpy.context.scene.labels_contures, hemi)


def object_coloring(obj, rgb):
    # print('ploting {} with {}'.format(obj.name, rgb))
    if not obj:
        print('object_coloring: obj is None!')
        return False
    bpy.context.scene.objects.active = obj
    # todo: do we need to select the object here? In diff mode it's a problem
    # obj.select = True
    cur_mat = obj.active_material
    new_color = (rgb[0], rgb[1], rgb[2], 1)
    cur_mat.diffuse_color = new_color[:3]
    if can_color_obj(obj):
        cur_mat.node_tree.nodes["RGB"].outputs[0].default_value = new_color
    # else:
    #     print("Can't color {}".format(obj.name))
    #     return False
    # new_color = get_obj_color(obj)
    # print('{} new color: {}'.format(obj.name, new_color))
    if _addon().is_solid():
        cur_mat.use_nodes = False
    else:
        cur_mat.use_nodes = True
    # print(cur_mat.diffuse_color)
    return True


def get_obj_color(obj):
    cur_mat = obj.active_material
    try:
        if can_color_obj(obj):
            cur_color = tuple(cur_mat.node_tree.nodes["RGB"].outputs[0].default_value)
        else:
            cur_color = (1, 1, 1)
    except:
        cur_color = (1, 1, 1)
        print("Can't get the color!")
    return cur_color


def clear_subcortical_fmri_activity():
    for sub_obj in bpy.data.objects['Subcortical_fmri_activity_map'].children:
        clear_object_vertex_colors(sub_obj)
    for sub_obj in bpy.data.objects['Subcortical_meg_activity_map'].children:
        object_coloring(sub_obj, (1, 1, 1))
    for sub_obj in bpy.data.objects['Subcortical_structures'].children:
        object_coloring(sub_obj, (1, 1, 1))


def clear_cortex(hemis=HEMIS):
    for hemi in hemis:
        for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
            clear_object_vertex_colors(cur_obj)
        # if bpy.context.scene.coloring_both_pial_and_inflated:
        #     for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
        #         clear_object_vertex_colors(cur_obj)
        # else:
        #     # if _addon().is_pial():
        #     #     cur_obj = bpy.data.objects[hemi]
        #     # elif _addon().is_inflated():
        #     cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
        #     clear_object_vertex_colors(cur_obj)
        for label_obj in bpy.data.objects['Cortex-{}'.format(hemi)].children:
            object_coloring(label_obj, (1, 1, 1))


#todo: call this code from the coloring
def clear_object_vertex_colors(cur_obj):
    mesh = cur_obj.data
    scn = bpy.context.scene
    scn.objects.active = cur_obj
    cur_obj.select = True
    # bpy.ops.mesh.vertex_color_remove()
    # vcol_layer = mesh.vertex_colors.new()
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        # mesh.vertex_colors.active_index = 1
        mesh.vertex_colors.active_index = mesh.vertex_colors.keys().index('Col')
    if not (len(mesh.vertex_colors) == 1 and 'inflated' in cur_obj.name):
        bpy.ops.mesh.vertex_color_remove()
    if mesh.vertex_colors.get('Col') is None:
        vcol_layer = mesh.vertex_colors.new('Col')
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        # mesh.vertex_colors.active_index = 1
        mesh.vertex_colors.active_index = mesh.vertex_colors.keys().index('Col')
        mesh.vertex_colors['Col'].active_render = True


# todo: do something with the threshold parameter
# @mu.timeit
def color_objects_homogeneously(data, names, conditions, data_min, colors_ratio, threshold=0, postfix_str=''):
    if data is None:
        print('color_objects_homogeneously: No data to color!')
        return
    if names is None:
        data, names, conditions = data['data'], data['names'], data['conditions']
    default_color = (1, 1, 1)
    cur_frame = bpy.context.scene.frame_current
    for obj_name, values in zip(names, data):
        if not isinstance(obj_name, str):
            obj_name = obj_name.astype(str)
        if values.ndim == 0:
            values = [values]
        t_ind = min(len(values) - 1, cur_frame)
        if values[t_ind].ndim == 0:
            value = values[t_ind]
        elif bpy.context.scene.selection_type == 'spec_cond':
            cond_inds = np.where(conditions == bpy.context.scene.conditions_selection)[0]
            if len(cond_inds) == 0:
                print("!!! Can't find the current condition in the data['conditions'] !!!")
                return
            else:
                cond_ind = cond_inds[0]
                object_colors = object_colors[:, cond_ind]
                value = values[t_ind, cond_ind]
        else:
            value = np.diff(values[t_ind])[0] if values.shape[1] > 1 else np.squeeze(values[t_ind])
        # todo: there is a difference between value and real_value, what should we do?
        # real_value = mu.get_fcurve_current_frame_val('Deep_electrodes', obj_name, cur_frame)
        # new_color = object_colors[cur_frame] if abs(value) > threshold else default_color
        new_color = calc_colors([value], data_min, colors_ratio)[0]
        # todo: check if the stat should be avg or diff
        obj = bpy.data.objects.get(obj_name+postfix_str)
        # if obj and not obj.hide:
        #     print('trying to color {} with {}'.format(obj_name+postfix_str, new_color))
        # obj.active_material = bpy.data.materials['selected_label_Mat_subcortical']
        ret = object_coloring(obj, new_color)
        # if not ret:
        #     print('color_objects_homogeneously: Error in coloring the object {}!'.format(obj_name))
            # print(obj_name, value, new_color)
        # else:
        #     print('color_objects_homogeneously: {} was not loaded!'.format(obj_name))

    # _addon().show_rois()
    # print('Finished coloring!!')


def init_activity_map_coloring(map_type, subcorticals=True):
    # _addon().set_appearance_show_activity_layer(bpy.context.scene, True)
    # _addon().set_filter_view_type(bpy.context.scene, 'RENDERS')
    _addon().show_activity()
    # _addon().change_to_rendered_brain()

    if not bpy.context.scene.objects_show_hide_sub_cortical:
        if subcorticals:
            _addon().show_hide_hierarchy(map_type != 'FMRI', 'Subcortical_fmri_activity_map')
            _addon().show_hide_hierarchy(map_type != 'MEG', 'Subcortical_meg_activity_map')
        else:
            _addon().show_hide_sub_corticals(not subcorticals)
    # change_view3d()


def load_faces_verts():
    faces_verts = {}
    current_root_path = mu.get_user_fol()
    if op.isfile(op.join(current_root_path, 'faces_verts_lh.npy') and \
                         op.join(current_root_path, 'faces_verts_rh.npy')):
        faces_verts['lh'] = np.load(op.join(current_root_path, 'faces_verts_lh.npy'))
        faces_verts['rh'] = np.load(op.join(current_root_path, 'faces_verts_rh.npy'))
    return faces_verts


def load_subs_faces_verts():
    faces_verts = {}
    verts = {}
    current_root_path = mu.get_user_fol()
    subcoticals = glob.glob(op.join(current_root_path, 'subcortical', '*_faces_verts.npy'))
    for subcortical_file in subcoticals:
        subcortical = mu.namebase(subcortical_file)[:-len('_faces_verts')]
        lookup_file = op.join(current_root_path, 'subcortical', '{}_faces_verts.npy'.format(subcortical))
        verts_file = op.join(current_root_path, 'subcortical', '{}.npz'.format(subcortical))
        if op.isfile(lookup_file) and op.isfile(verts_file):
            faces_verts[subcortical] = np.load(lookup_file)
            verts[subcortical] = np.load(verts_file)['verts']
    return faces_verts, verts


def load_meg_subcortical_activity():
    meg_sub_activity = None
    subcortical_activity_file = op.join(mu.get_user_fol(), 'subcortical_meg_activity.npz')
    if op.isfile(subcortical_activity_file) and bpy.context.scene.coloring_meg_subcorticals:
        meg_sub_activity = np.load(subcortical_activity_file)
    return meg_sub_activity


@mu.dump_args
def activity_map_coloring(map_type, clusters=False, threshold=None):
    init_activity_map_coloring(map_type)
    if threshold is None:
        threshold = bpy.context.scene.coloring_threshold
    meg_sub_activity = None
    if map_type == 'MEG':
        if bpy.context.scene.coloring_meg_subcorticals:
            meg_sub_activity = load_meg_subcortical_activity()
        ColoringMakerPanel.what_is_colored.add(WIC_MEG)
        mu.remove_items_from_set(ColoringMakerPanel.what_is_colored, [WIC_FMRI, WIC_FMRI_CLUSTERS, WIC_FMRI_DYNAMICS])
        plot_subcorticals = bpy.context.scene.coloring_meg_subcorticals
    elif map_type == 'FMRI':
        if not clusters:
            ColoringMakerPanel.what_is_colored.add(WIC_FMRI)
        else:
            ColoringMakerPanel.what_is_colored.add(WIC_FMRI_CLUSTERS)
        mu.remove_items_from_set(ColoringMakerPanel.what_is_colored, [WIC_MEG, WIC_MEG_LABELS, WIC_FMRI_DYNAMICS])
        plot_subcorticals = False
    elif map_type == 'FMRI_DYNAMICS':
        ColoringMakerPanel.what_is_colored.add(WIC_FMRI_DYNAMICS)
        mu.remove_items_from_set(ColoringMakerPanel.what_is_colored, [WIC_MEG, WIC_MEG_LABELS, WIC_FMRI, WIC_FMRI_CLUSTERS])
        # todo: support in subcorticals
        plot_subcorticals = False
    return plot_activity(map_type, ColoringMakerPanel.faces_verts, threshold, meg_sub_activity, clusters=clusters,
                  plot_subcorticals=plot_subcorticals)
    # setup_environment_settings()


def meg_labels_coloring(override_current_mat=True):
    ColoringMakerPanel.what_is_colored.add(WIC_MEG_LABELS)
    init_activity_map_coloring('MEG')
    threshold = bpy.context.scene.coloring_threshold
    hemispheres = [hemi for hemi in HEMIS if not bpy.data.objects[hemi].hide]
    user_fol = mu.get_user_fol()
    atlas, em = bpy.context.scene.atlas, bpy.context.scene.meg_labels_extract_method
    labels_data_minimax = np.load(op.join(user_fol, 'meg', 'meg_labels_{}_{}_minmax.npz'.format(atlas, em)))
    meg_labels_min, meg_labels_max = labels_data_minimax['labels_diff_minmax'] \
        if bpy.context.scene.meg_labels_coloring_type == 'diff' else labels_data_minimax['labels_minmax']
    data_minmax = max(map(abs, [meg_labels_max, meg_labels_min]))
    meg_labels_min, meg_labels_max = -data_minmax, data_minmax
    for hemi in hemispheres:
        labels_data = np.load(op.join(user_fol, 'meg', 'labels_data_{}_{}_{}.npz'.format(atlas, em, hemi)))
        labels_coloring_hemi(
            labels_data, ColoringMakerPanel.faces_verts, hemi, threshold, bpy.context.scene.meg_labels_coloring_type,
            override_current_mat, meg_labels_min, meg_labels_max)


def color_connections_labels_avg(override_current_mat=True):
    ColoringMakerPanel.what_is_colored.add(WIC_CONN_LABELS_AVG)
    init_activity_map_coloring('MEG')
    threshold = bpy.context.scene.coloring_threshold
    hemispheres = [hemi for hemi in HEMIS if not bpy.data.objects[hemi].hide]
    user_fol = mu.get_user_fol()
    # files_names = [mu.namebase(fname).replace('_', ' ').replace('{} '.format(atlas), '') for fname in
    #                conn_labels_avg_files]
    atlas = bpy.context.scene.atlas
    # labels_data_minimax = np.load(op.join(user_fol, 'meg', 'meg_labels_{}_{}_minmax.npz'.format(atlas, em)))
    # meg_labels_min, meg_labels_max = labels_data_minimax['labels_diff_minmax'] \
    #     if bpy.context.scene.meg_labels_coloring_type == 'diff' else labels_data_minimax['labels_minmax']
    # data_minmax = max(map(abs, [meg_labels_max, meg_labels_min]))
    # meg_labels_min, meg_labels_max = -data_minmax, data_minmax

    file_name = bpy.context.scene.conn_labels_avg_files.replace(' ', '_').replace('_labels_avg.npz', '')
    file_name = '{}_{}_labels_avg.npz'.format(file_name, atlas)
    data = np.load(op.join(user_fol, 'connectivity', file_name))
    for hemi in hemispheres:
        labels_coloring_hemi(
            labels_data, ColoringMakerPanel.faces_verts, hemi, threshold, bpy.context.scene.meg_labels_coloring_type,
            override_current_mat, meg_labels_min, meg_labels_max)


def color_connectivity_degree():
    corr = ColoringMakerPanel.static_conn
    threshold = bpy.context.scene.connectivity_degree_threshold
    labels = ColoringMakerPanel.connectivity_labels
    if bpy.context.scene.connectivity_degree_threshold_use_abs:
        degree_mat = np.sum(abs(corr) >= threshold, 0)
    else:
        degree_mat = np.sum(corr >= threshold, 0)
    data_max = max(degree_mat)
    colors_ratio = 256 / (data_max)
    _addon().set_colorbar_max_min(data_max, 0)
    _addon().set_colormap('YlOrRd')
    _addon().set_colorbar_title('fMRI connectivity degree')
    # _addon().fix_labels_material(labels)

    color_objects_homogeneously(degree_mat, labels, ['rest'], 0, colors_ratio)
    _addon().show_rois()
    if bpy.context.scene.connectivity_degree_save_image:
        _addon().save_image()


def static_conn_files_update(self, context):
    ColoringMakerPanel.static_conn = np.load(op.join(mu.get_user_fol(), 'connectivity', '{}.npy'.format(
        bpy.context.scene.static_conn_files)))


def update_connectivity_degree_threshold(self, context):
    color_connectivity_degree()


def fmri_labels_coloring(override_current_mat=True):
    ColoringMakerPanel.what_is_colored.add(WIC_FMRI_LABELS)
    if not bpy.context.scene.color_rois_homogeneously:
        init_activity_map_coloring('FMRI')
    threshold = bpy.context.scene.coloring_threshold
    hemispheres = [hemi for hemi in HEMIS if not bpy.data.objects[hemi].hide]
    user_fol = mu.get_user_fol()
    atlas, em = bpy.context.scene.atlas, bpy.context.scene.fmri_labels_extract_method
    if _addon().colorbar_values_are_locked():
        labels_min, labels_max = _addon().get_colorbar_max_min()
    else:
        labels_min, labels_max = np.load(
            op.join(user_fol, 'fmri', 'labels_data_{}_{}_minmax.pkl'.format(atlas, em)))
        if labels_min > 0:
            labels_min = 0
        _addon().set_colorbar_max_min(labels_max, labels_min)
    colors_ratio = 256 / (labels_max - labels_min)
    set_default_colormap(labels_min, labels_max)
    for hemi in hemispheres:
        if bpy.data.objects['inflated_{}'.format(hemi)].hide:
            continue
        labels_data = np.load(op.join(user_fol, 'fmri', 'labels_data_{}_{}_{}.npz'.format(atlas, em, hemi)))
        # fix_labels_material(labels_data['names'])
        # todo check this also in other labels coloring
        if bpy.context.scene.color_rois_homogeneously:
            color_objects_homogeneously(
                labels_data['data'], labels_data['names'], ['rest'], labels_min, colors_ratio, threshold)
            _addon().show_rois()
        else:
            labels_coloring_hemi(
                labels_data, ColoringMakerPanel.faces_verts, hemi, threshold, 'avg', override_current_mat,
                labels_min, labels_max)

    if ColoringMakerPanel.fmri_subcorticals_mean_exist:
        em = bpy.context.scene.fmri_labels_extract_method
        subs_data = np.load(op.join(user_fol, 'fmri', 'subcorticals_{}.npz'.format(em)))
        # fix_labels_material(subs_data['names'])
        if bpy.context.scene.color_rois_homogeneously:
            color_objects_homogeneously(
                subs_data['data'], subs_data['names'], ['rest'], labels_min, colors_ratio, threshold)
            _addon().show_rois()
        else:
            t = bpy.context.scene.frame_current
            for sub_name, sub_data in zip(subs_data['names'], subs_data['data']):
                verts = ColoringMakerPanel.subs_verts[sub_name]
                data = np.tile(sub_data[t], (len(verts), 1))
                cur_obj = bpy.data.objects.get('{}_fmri_activity'.format(sub_name))
                activity_map_obj_coloring(
                    cur_obj, data, ColoringMakerPanel.subs_faces_verts[sub_name], 0, True,
                    labels_min, colors_ratio)


def labels_coloring_hemi(labels_data, faces_verts, hemi, threshold=0, labels_coloring_type='diff',
                         override_current_mat=True, colors_min=None, colors_max=None):
    now = time.time()
    colors_ratio = None
    labels_names = ColoringMakerPanel.labels_vertices['labels_names']
    labels_vertices = ColoringMakerPanel.labels_vertices['labels_vertices']
    vertices_num = max(itertools.chain.from_iterable(labels_vertices[hemi])) + 1
    no_t = labels_data['data'][0].ndim == 0
    t = bpy.context.scene.frame_current
    if not colors_min is None and not colors_max is None:
        colors_data = np.zeros((vertices_num))
    else:
        colors_data = np.ones((vertices_num, 4))
        colors_data[:, 0] = 0
    colors = labels_data['colors'] if 'colors' in labels_data else [None] * len(labels_data['names'])
    if not colors_min is None and not colors_max is None:
        if _addon().colorbar_values_are_locked():
            colors_max, colors_min = _addon().get_colorbar_max_min()
            colors_ratio = 256 / (colors_max - colors_min)
        else:
            colors_ratio = 256 / (colors_max - colors_min)
            _addon().set_colorbar_max_min(colors_max, colors_min)
    for label_data, label_colors, label_name in zip(labels_data['data'], colors, labels_data['names']):
        label_name = mu.to_str(label_name)
        if label_data.ndim == 0:
            label_data = np.array([label_data])
        if not colors_min is None and not colors_max is None:
            if label_data.ndim > 1:
                if labels_coloring_type == 'diff':
                    if label_data.squeeze().ndim == 1:
                        labels_data = label_data.squeeze()
                    else:
                        label_data = np.squeeze(np.diff(label_data))
                else:
                    cond_ind = np.where(labels_data['conditions'] == labels_coloring_type)[0]
                    label_data = np.squeeze(label_data[:, cond_ind])
            label_colors = calc_colors(label_data, colors_min, colors_ratio)
        else:
            label_colors = np.array(label_colors)
            if 'unknown' in label_name:
                continue
            # if label_colors.ndim == 3:
        #         cond_inds = np.where(labels_data['conditions'] == bpy.context.scene.conditions_selection)[0]
        #         if len(cond_inds) == 0:
        #             print("!!! Can't find the current condition in the data['conditions'] !!!")
        #             return
        #         label_colors = label_colors[:, cond_inds[0], :]
        #         label_data = label_data[:, cond_inds[0]]
        if label_name not in labels_names[hemi]:
            continue
        label_index = labels_names[hemi].index(label_name)
        label_vertices = np.array(labels_vertices[hemi][label_index])
        if len(label_vertices) > 0:
            if no_t:
                label_data_t, label_colors_t = label_data, label_colors
            else:
                label_data_t, label_colors_t = (label_data[t], label_colors[t]) if 0 < t < len(label_data) else (0, 0)
            # print('coloring {} with {}'.format(label_name, label_colors_t))
            if not colors_min is None and not colors_max is None:
                colors_data[label_vertices] = label_data_t
            else:
                label_colors_data = np.hstack((label_data_t, label_colors_t))
                label_colors_data = np.tile(label_colors_data, (len(label_vertices), 1))
                colors_data[label_vertices, :] = label_colors_data
    # if bpy.context.scene.coloring_both_pial_and_inflated:
    #     for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
    #         activity_map_obj_coloring(
    #             cur_obj, colors_data, faces_verts[hemi], threshold, override_current_mat, colors_min, colors_ratio)
    # else:
    #     if _addon().is_pial():
    #         cur_obj = bpy.data.objects[hemi]
    #     elif _addon().is_inflated():
    #         cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
    #     activity_map_obj_coloring(
    #         cur_obj, colors_data, faces_verts[hemi], threshold, override_current_mat, colors_min, colors_ratio)
    cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
    activity_map_obj_coloring(
        cur_obj, colors_data, faces_verts[hemi], threshold, override_current_mat, colors_min, colors_ratio)
    print('Finish labels_coloring_hemi, hemi {}, {:.2f}s'.format(hemi, time.time()-now))


def color_contours(specific_label='', specific_hemi='both'):
    d = ColoringMakerPanel.labels_contures
    contour_max = max([d[hemi]['max'] for hemi in mu.HEMIS])
    if not _addon().colorbar_values_are_locked():
        _addon().set_colormap('jet')
        _addon().set_colorbar_title('{} labels contours'.format(bpy.context.scene.contours_coloring))
        _addon().set_colorbar_max_min(contour_max, 1)
        _addon().set_colorbar_prec(0)
    _addon().show_activity()
    for hemi in mu.HEMIS:
        contours = d[hemi]['contours']
        if specific_hemi != 'both' and hemi != specific_hemi:
            contours = np.zeros(contours.shape)
        elif specific_label != '':
            label_ind = np.where(d[hemi]['labels'] == specific_label)
            if len(label_ind) > 0:
                contours[np.where(contours != label_ind[0][0] + 1)] = 0
        color_hemi_data(hemi, contours, 0.1, 256 / contour_max, override_current_mat=False)


def color_hemi_data(hemi, data, data_min=None, colors_ratio=None, threshold=0, override_current_mat=True):
    if bpy.data.objects['inflated_{}'.format(hemi)].hide:
        return
    faces_verts = ColoringMakerPanel.faces_verts[hemi]
    # if bpy.context.scene.coloring_both_pial_and_inflated:
    #     for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
    #         activity_map_obj_coloring(
    #             cur_obj, data, faces_verts, threshold, override_current_mat, data_min, colors_ratio)
    # else:
    #     # if _addon().is_pial():
    #     #     cur_obj = bpy.data.objects[hemi]
    #     # elif _addon().is_inflated():
    #     cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
    #     activity_map_obj_coloring(cur_obj, data, faces_verts, threshold, override_current_mat, data_min, colors_ratio)
    cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
    activity_map_obj_coloring(cur_obj, data, faces_verts, threshold, override_current_mat, data_min, colors_ratio)


@mu.timeit
def plot_activity(map_type, faces_verts, threshold, meg_sub_activity=None,
        plot_subcorticals=True, override_current_mat=True, clusters=False):

    current_root_path = mu.get_user_fol() # bpy.path.abspath(bpy.context.scene.conf_path)
    not_hiden_hemis = [hemi for hemi in HEMIS if not bpy.data.objects['inflated_{}'.format(hemi)].hide]
    t = bpy.context.scene.frame_current
    frame_str = str(t)
    data_min, data_max = 0, 0
    f = None
    for hemi in not_hiden_hemis:
        colors_ratio, data_min = None, None
        if map_type in ['MEG', 'FMRI_DYNAMICS']:
            if map_type == 'MEG':
                activity_type = bpy.context.scene.meg_files
                activity_type = '' if activity_type == 'conditions diff' else '{}_'.format(activity_type)
                fname = op.join(current_root_path, 'activity_map_{}{}'.format(
                    activity_type, hemi), 't' + frame_str + '.npy')
                colors_ratio = ColoringMakerPanel.meg_activity_colors_ratio
                data_min, data_max = ColoringMakerPanel.meg_activity_data_minmax
                cb_title = 'MEG'
            elif map_type == 'FMRI_DYNAMICS':
                fname =  op.join(current_root_path, 'fmri', 'activity_map_' + hemi, 't' + frame_str + '.npy')
                colors_ratio = ColoringMakerPanel.fmri_activity_colors_ratio
                data_min, data_max = ColoringMakerPanel.fmri_activity_data_minmax
                cb_title = 'fMRI'
            if op.isfile(fname):
                f = np.load(fname)
                if _addon().colorbar_values_are_locked():
                    data_max, data_min = _addon().get_colorbar_max_min()
                    colors_ratio = 256 / (data_max - data_min)
                _addon().set_colorbar_max_min(data_max, data_min)
                _addon().set_colorbar_title(cb_title)
            else:
                print("Can't load {}".format(fname))
                return False
        elif map_type == 'FMRI':
            if not ColoringMakerPanel.fmri_activity_data_minmax is None:
                if _addon().colorbar_values_are_locked():
                    data_max, data_min = _addon().get_colorbar_max_min()
                    colors_ratio = 256 / (data_max - data_min)
                else:
                    colors_ratio = ColoringMakerPanel.fmri_activity_colors_ratio
                    data_min, data_max = ColoringMakerPanel.fmri_activity_data_minmax
                    _addon().set_colorbar_max_min(data_max, data_min)
                _addon().set_colorbar_title('fMRI')
            if clusters:
                f = [c for h, c in ColoringMakerPanel.fMRI_clusters.items() if h == hemi]
            else:
                f = ColoringMakerPanel.fMRI[hemi]

        if threshold > data_max:
            print('Threshold > data_max, changing it to data_min')
            threshold = data_min

        if f.ndim == 2:
            if t >= f.shape[1]:
                bpy.context.scene.frame_current = t = f.shape[1] - 1
                bpy.data.scenes['Scene'].frame_preview_start = 0
                bpy.data.scenes['Scene'].frame_preview_end = t
            f = f[:, t]

        # todo: should read default values from ini file
        if not (data_min == 0 and data_max == 0) and not _addon().colorbar_values_are_locked():
            if data_min == 0:
                _addon().set_colormap('YlOrRd')
            else:
                _addon().set_colormap('BuPu-YlOrRd')

        color_hemi_data(hemi, f, data_min, colors_ratio, threshold, override_current_mat)
        # if bpy.context.scene.coloring_both_pial_and_inflated:
        #     for cur_obj in [bpy.data.objects[hemi], bpy.data.objects['inflated_{}'.format(hemi)]]:
        #         activity_map_obj_coloring(cur_obj, f, faces_verts[hemi], threshold, override_current_mat, data_min,
        #                                   colors_ratio)
        # else:
        #     if _addon().is_pial():
        #         cur_obj = bpy.data.objects[hemi]
        #     elif _addon().is_inflated():
        #         cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
        #     activity_map_obj_coloring(cur_obj, f, faces_verts[hemi], threshold, override_current_mat, data_min, colors_ratio)

    if plot_subcorticals and not bpy.context.scene.objects_show_hide_sub_cortical and not meg_sub_activity is None:
        if map_type == 'MEG' and not bpy.data.objects['Subcortical_meg_activity_map'].hide:
                if f is None:
                    if _addon().colorbar_values_are_locked():
                        data_max, data_min = _addon().get_colorbar_max_min()
                        colors_ratio = 256 / (data_max - data_min)
                    else:
                        data_max, data_min = meg_sub_activity['data_minmax'], -meg_sub_activity['data_minmax']
                        colors_ratio = 256 / (2 * data_max)
                        _addon().set_colorbar_max_min(data_max, data_min)
                    _addon().set_colorbar_title('Subcortical MEG')
                color_objects_homogeneously(
                    meg_sub_activity['data'], meg_sub_activity['names'], meg_sub_activity['conditions'], data_min,
                    colors_ratio, threshold, '_meg_activity')
                _addon().show_rois()
        elif map_type == 'FMRI' and not bpy.data.objects['Subcortical_fmri_activity_map'].hide:
            fmri_subcortex_activity_color(threshold, override_current_mat)

    return True
    # return loop_indices
    # Noam: not sure this is necessary
    #deselect_all()
    #bpy.data.objects['Brain'].select = True


def fmri_subcortex_activity_color(threshold, override_current_mat=True):
    current_root_path = mu.get_user_fol() # bpy.path.abspath(bpy.context.scene.conf_path)
    subcoticals = glob.glob(op.join(current_root_path, 'subcortical_fmri_activity', '*.npy'))
    for subcortical_file in subcoticals:
        subcortical = op.splitext(op.basename(subcortical_file))[0]
        cur_obj = bpy.data.objects.get('{}_fmri_activity'.format(subcortical))
        if cur_obj is None:
            print("Can't find the object {}!".format(subcortical))
        else:
            lookup_file = op.join(current_root_path, 'subcortical', '{}_faces_verts.npy'.format(subcortical))
            verts_file = op.join(current_root_path, 'subcortical_fmri_activity', '{}.npy'.format(subcortical))
            if op.isfile(lookup_file) and op.isfile(verts_file):
                lookup = np.load(lookup_file)
                verts_values = np.load(verts_file)
                activity_map_obj_coloring(cur_obj, verts_values, lookup, threshold, override_current_mat)


def create_inflated_curv_coloring():

    def color_obj_curvs(cur_obj, curv, lookup):
        mesh = cur_obj.data
        if not 'curve' in mesh.vertex_colors.keys():
            scn = bpy.context.scene
            verts_colors = np.zeros((curv.shape[0], 3))
            verts_colors[np.where(curv == 0)] = [1, 1, 1]
            verts_colors[np.where(curv == 1)] = [0.55, 0.55, 0.55]
            scn.objects.active = cur_obj
            cur_obj.select = True
            bpy.ops.mesh.vertex_color_remove()
            vcol_layer = mesh.vertex_colors.new('curve')
            for vert in range(curv.shape[0]):
                x = lookup[vert]
                for loop_ind in x[x>-1]:
                    d = vcol_layer.data[loop_ind]
                    d.color = verts_colors[vert]

    try:
        # todo: check not to overwrite
        print('Creating the inflated curvatures coloring')
        for hemi in mu.HEMIS:
            cur_obj = bpy.data.objects['inflated_{}'.format(hemi)]
            curv_fname = op.join(mu.get_user_fol(), 'surf', '{}.curv.npy'.format(hemi))
            faces_verts_fname = op.join(mu.get_user_fol(), 'faces_verts_{}.npy'.format(hemi))
            if not op.isfile(curv_fname) or not op.isfile(faces_verts_fname):
                print("Can't plot the {} curves!".format(hemi))
                continue
            curv = np.load(curv_fname)
            lookup = np.load(op.join(mu.get_user_fol(), 'faces_verts_{}.npy'.format(hemi)))
            color_obj_curvs(cur_obj, curv, lookup)
        for hemi in mu.HEMIS:
            curvs_fol = op.join(mu.get_user_fol(), 'surf', '{}_{}_curves'.format(bpy.context.scene.atlas, hemi))
            lookup_fol = op.join(mu.get_user_fol(), 'labels', '{}.pial.{}'.format(bpy.context.scene.atlas, hemi))
            for cur_obj in bpy.data.objects['Cortex-{}'.format(hemi)].children:
                try:
                    label = cur_obj.name
                    inflated_cur_obj = bpy.data.objects['inflated_{}'.format(label)]
                    curv_file = op.join(curvs_fol, '{}_curv.npy'.format(label))
                    if op.isfile(curv_file):
                        curv = np.load(curv_file)
                    else:
                        print('Can\'t find the file {}'.format(curv_file))

                    faces_verts_file = op.join(lookup_fol, '{}_faces_verts.npy'.format(label))
                    if op.isfile(faces_verts_file):
                        lookup = np.load(faces_verts_file)
                    else:
                        print('Can\'t find the file {}'.format(faces_verts_file))
                    color_obj_curvs(inflated_cur_obj, curv, lookup)
                except:
                    print("Can't create {}'s curves!".format(cur_obj.name))
                    print(traceback.format_exc())
    except:
        print('Error in create_inflated_curv_coloring!')
        print(traceback.format_exc())


def calc_colors(vert_values, data_min, colors_ratio, cm=None):
    if cm is None:
        cm = _addon().get_cm()
    if cm is None:
        return np.zeros((len(vert_values), 3))
    colors_indices = ((np.array(vert_values) - data_min) * colors_ratio).astype(int)
    # take care about values that are higher or smaller than the min and max values that were calculated (maybe using precentiles)
    colors_indices[colors_indices < 0] = 0
    colors_indices[colors_indices > 255] = 255
    verts_colors = cm[colors_indices]
    return verts_colors


# @mu.timeit
def activity_map_obj_coloring(cur_obj, vert_values, lookup, threshold, override_current_mat, data_min=None,
                              colors_ratio=None, bigger_or_equall=False):
    mesh = cur_obj.data
    scn = bpy.context.scene

    values = vert_values[:, 0] if vert_values.ndim > 1 else vert_values
    if bigger_or_equall:
        valid_verts = np.where(np.abs(values) >= threshold)[0]
    else:
        valid_verts = np.where(np.abs(values) > threshold)[0]
    colors_picked_from_cm = False
    # cm = _addon().get_cm()
    if vert_values.ndim > 1 and vert_values.squeeze().ndim == 1:
        vert_values = vert_values.squeeze()
    if vert_values.ndim == 1 and not data_min is None:
        verts_colors = calc_colors(vert_values, data_min, colors_ratio)
        colors_picked_from_cm = True
    #check if our mesh already has Vertex Colors, and if not add some... (first we need to make sure it's the active object)
    scn.objects.active = cur_obj
    cur_obj.select = True
    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        # mesh.vertex_colors.active_index = 1
        mesh.vertex_colors.active_index = mesh.vertex_colors.keys().index('Col')
    if not (len(mesh.vertex_colors) == 1 and 'inflated' in cur_obj.name):
        c = mu.get_graph_context()
        bpy.ops.mesh.vertex_color_remove(c)
        # except:
        #     print("Can't remove vertex color!")
    if mesh.vertex_colors.get('Col') is None:
        vcol_layer = mesh.vertex_colors.new('Col')
    # vcol_layer = mesh.vertex_colors["Col"]

    if len(mesh.vertex_colors) > 1 and 'inflated' in cur_obj.name:
        # mesh.vertex_colors.active_index = 1
        mesh.vertex_colors.active_index = mesh.vertex_colors.keys().index('Col')
        mesh.vertex_colors['Col'].active_render = True
    # else:
    vcol_layer = mesh.vertex_colors.active
    # print('cur_obj: {}, max vert in lookup: {}, vcol_layer len: {}'.format(cur_obj.name, np.max(lookup), len(vcol_layer.data)))
    vcol_layer = mesh.vertex_colors['Col']
    if colors_picked_from_cm:
        verts_lookup_loop_coloring(valid_verts, lookup, vcol_layer, lambda vert:verts_colors[vert])
    else:
        verts_lookup_loop_coloring(valid_verts, lookup, vcol_layer, lambda vert:vert_values[vert, 1:])

    # for vert in valid_verts:
    #     x = lookup[vert]
    #     for loop_ind in x[x > -1]:
    #         d = vcol_layer.data[loop_ind]
    #         if vert_values.ndim == 1:  # colors_picked_from_cm:
    #             colors = verts_colors[vert]
    #         else:
    #             colors = vert_values[vert, 1:]
    #         d.color = colors


def verts_lookup_loop_coloring(valid_verts, lookup, vcol_layer, colors_func):
    for vert in valid_verts:
        x = lookup[vert]
        for loop_ind in x[x > -1]:
            d = vcol_layer.data[loop_ind]
            d.color = colors_func(vert)


def color_groups_manually():
    ColoringMakerPanel.what_is_colored.add(WIC_GROUPS)
    init_activity_map_coloring('FMRI')
    labels = ColoringMakerPanel.labels_groups[bpy.context.scene.labels_groups]
    objects_names, colors, data = defaultdict(list), defaultdict(list), defaultdict(list)
    for label in labels:
        obj_type = mu.check_obj_type(label['name'])
        if obj_type is not None:
            objects_names[obj_type].append(label['name'])
            colors[obj_type].append(np.array(label['color']) / 255.0)
            data[obj_type].append(1.)
    clear_subcortical_fmri_activity()
    color_objects(objects_names, colors, data)


def color_manually():
    ColoringMakerPanel.what_is_colored.add(WIC_MANUALLY)
    init_activity_map_coloring('FMRI')
    subject_fol = mu.get_user_fol()
    objects_names, colors, data = defaultdict(list), defaultdict(list), defaultdict(list)
    values = []
    coloring_objects, coloring_labels = False, False
    rand_colors = cu.get_distinct_colors(30)
    labels_delim, labels_pos, _, _ = mu.get_hemi_delim_and_pos(bpy.data.objects['Cortex-lh'].children[0].name)
    coloring_name = '{}.csv'.format(bpy.context.scene.coloring_files)
    if coloring_name.startswith('_labels_'):
        atlas = coloring_name.split('_')[2]
        obj_type = mu.OBJ_TYPE_LABEL
        coloring_labels = True
    else:
        obj_type = ''
        coloring_objects = True
    for line in mu.csv_file_reader(op.join(subject_fol, 'coloring', coloring_name)):
        if len(line) == 0:
            continue
        obj_name, color_name = line[0], line[1:4]
        if len(line) == 5:
            values.append(float(line[4]))
        if obj_name[0] == '#':
            continue
        if isinstance(color_name, list) and len(color_name) == 1:
            color_name = color_name[0]
        if obj_type == '':
            obj_type = mu.check_obj_type(obj_name)
        if obj_type is None:
            delim, pos, label, hemi = mu.get_hemi_delim_and_pos(obj_name)
            if delim != '' and pos != '' and hemi != '' and label != obj_name:
                obj_name = mu.build_label_name(labels_delim, labels_pos, label, hemi)
                obj_type = mu.check_obj_type(obj_name)
        if isinstance(color_name, str) and color_name.startswith('mark'):
            import filter_panel
            filter_panel.filter_roi_func(obj_name, mark=color_name)
        else:
            if isinstance(color_name, str):
                color_rgb = cu.name_to_rgb(color_name)
            # Check if the color is already in RBG
            elif len(color_name) == 3:
                color_rgb = color_name
            elif len(color_name) == 0:
                color_rgb = next(rand_colors)
            else:
                print('Unrecognize color! ({})'.format(color_name))
                continue
            color_rgb = list(map(float, color_rgb))
            if obj_type is not None:
                objects_names[obj_type].append(obj_name)
                colors[obj_type].append(color_rgb)
                data[obj_type].append(1.)

    if coloring_objects:
        color_objects(objects_names, colors, data)
    elif coloring_labels:
        plot_labels(objects_names[mu.OBJ_TYPE_LABEL], colors[mu.OBJ_TYPE_LABEL], atlas)

    if len(values) > 0:
        _addon().set_colorbar_max_min(np.max(values), np.min(values))
    _addon().set_colorbar_title(bpy.context.scene.coloring_files.replace('_', ' '))

    if op.isfile(op.join(subject_fol, 'coloring', '{}_legend.jpg'.format(bpy.context.scene.coloring_files))):
        cmd = '{} -m src.preproc.electrodes_preproc -s {} -a {} -f show_labeling_coloring'.format(
            bpy.context.scene.python_cmd, mu.get_user(), bpy.context.scene.atlas)
        print('Running {}'.format(cmd))
        mu.run_command_in_new_thread(cmd, False)


def color_objects(objects_names, colors, data):
    for hemi in HEMIS:
        obj_type = mu.OBJ_TYPE_CORTEX_LH if hemi=='lh' else mu.OBJ_TYPE_CORTEX_RH
        if obj_type not in objects_names or len(objects_names[obj_type]) == 0:
            continue
        labels_data = dict(data=np.array(data[obj_type]), colors=colors[obj_type], names=objects_names[obj_type])
        # print('color hemi {}: {}'.format(hemi, labels_names))
        labels_coloring_hemi(labels_data, ColoringMakerPanel.faces_verts, hemi, labels_coloring_type='avg')
    clear_subcortical_regions()
    if mu.OBJ_TYPE_SUBCORTEX in objects_names:
        for region, color in zip(objects_names[mu.OBJ_TYPE_SUBCORTEX], colors[mu.OBJ_TYPE_SUBCORTEX]):
            print('color {}: {}'.format(region, color))
            color_subcortical_region(region, color)
    if mu.OBJ_TYPE_ELECTRODE in objects_names:
        for electrode, color in zip(objects_names[mu.OBJ_TYPE_ELECTRODE], colors[mu.OBJ_TYPE_ELECTRODE]):
            obj = bpy.data.objects.get(electrode)
            if obj and not obj.hide:
                object_coloring(obj, color)
    if mu.OBJ_TYPE_CEREBELLUM in objects_names:
        for cer, color in zip(objects_names[mu.OBJ_TYPE_CEREBELLUM], colors[mu.OBJ_TYPE_CEREBELLUM]):
            obj = bpy.data.objects.get(cer)
            if obj and not obj.hide:
                object_coloring(obj, color)
    bpy.context.scene.subcortical_layer = 'fmri'
    _addon().show_activity()


def color_volumetric():
    ColoringMakerPanel.what_is_colored.add(WIC_VOLUMES)
    pass


def color_subcortical_region(region_name, color):
    #todo: read the ColoringPanel.subs_verts_faces like in fmri labels coloring
    cur_obj = bpy.data.objects.get(region_name + '_fmri_activity', None)
    obj_ana_fname = op.join(mu.get_user_fol(), 'subcortical', '{}.npz'.format(region_name))
    obj_lookup_fname = op.join(mu.get_user_fol(), 'subcortical', '{}_faces_verts.npy'.format(region_name))
    if not cur_obj is None and op.isfile(obj_lookup_fname):
        # todo: read only the verts number
        if not op.isfile(obj_ana_fname):
            verts, faces = mu.read_ply_file(op.join(mu.get_user_fol(), 'subcortical', '{}.ply'.format(region_name)))
            np.savez(obj_ana_fname, verts=verts, faces=faces)
        else:
            d = np.load(obj_ana_fname)
            verts =  d['verts']
        lookup = np.load(obj_lookup_fname)
        region_colors_data = np.hstack((np.array([1.]), color))
        region_colors_data = np.tile(region_colors_data, (len(verts), 1))
        activity_map_obj_coloring(cur_obj, region_colors_data, lookup, 0, True)
    else:
        if cur_obj and not 'white' in cur_obj.name.lower():
            print("Don't have the necessary files for coloring {}!".format(region_name))


def clear_subcortical_regions():
    clear_colors_from_parent_childrens('Subcortical_meg_activity_map')
    clear_subcortical_fmri_activity()


def clear_colors_from_parent_childrens(parent_object):
    parent_obj = bpy.data.objects.get(parent_object)
    if parent_obj is not None:
        for obj in parent_obj.children:
            if 'RGB' in obj.active_material.node_tree.nodes:
                obj.active_material.node_tree.nodes['RGB'].outputs['Color'].default_value = (1, 1, 1, 1)
            obj.active_material.diffuse_color = (1, 1, 1)


def default_coloring(loop_indices):
    for hemi, indices in loop_indices.items():
        cur_obj = bpy.data.objects[hemi]
        mesh = cur_obj.data
        vcol_layer = mesh.vertex_colors.active
        for loop_ind in indices:
            vcol_layer.data[loop_ind].color = [1, 1, 1]


def meg_files_update(self, context):
    _meg_files_update(context)


def _meg_files_update(context):
    user_fol = mu.get_user_fol()
    ColoringMakerPanel.activity_map_chosen = False
    ColoringMakerPanel.stc_file_chosen = False
    activity_types = [mu.namebase(f)[len('activity_map_'):-2] for f in glob.glob(op.join(user_fol, 'activity_map_*rh'))]
    for activity_type in activity_types:
        if activity_type != '':
            activity_type = activity_types[:-1]
        if bpy.context.scene.meg_files == activity_type or activity_type == '' and \
                        bpy.context.scene.meg_files == 'conditions diff':
            ColoringMakerPanel.activity_map_chosen = True
            meg_data_maxmin_fname = op.join(mu.get_user_fol(), 'meg_activity_map_{}minmax.pkl'.format(activity_type))
            data_min, data_max = mu.load(meg_data_maxmin_fname)
            ColoringMakerPanel.meg_activity_colors_ratio = 256 / (data_max - data_min)
            ColoringMakerPanel.meg_activity_data_minmax = (data_min, data_max)
            if not _addon().colorbar_values_are_locked():
                _addon().set_colorbar_max_min(data_max, data_min, True)
            break
    else:
        full_stc_fname = ''
        template = op.join(user_fol, 'meg', '*.stc')
        stcs_files = glob.glob(template)
        for stc_file in stcs_files:
            _, _, label, hemi = mu.get_hemi_delim_and_pos(mu.namebase(stc_file))
            if label == bpy.context.scene.meg_files:
                full_stc_fname = stc_file
                ColoringMakerPanel.stc_file_chosen = True
                break

        if full_stc_fname == '':
            print("Can't find the stc file in {}".format(template))
        else:
            ColoringMakerPanel.stc = mne.read_source_estimate(full_stc_fname)
            T = ColoringMakerPanel.stc.data.shape[1] - 1
            bpy.data.scenes['Scene'].frame_preview_start = 0
            bpy.data.scenes['Scene'].frame_preview_end = T
            if context.scene.frame_current > T:
                context.scene.frame_current = T
            data_min, data_max = calc_stc_minmax()
            _addon().set_colorbar_max_min(data_max, data_min)
            _addon().set_colorbar_title('MEG')
            # try:
            #     bpy.context.scene.meg_max_t = max([np.argmax(np.max(stc.rh_data, 0)), np.argmax(np.max(stc.lh_data, 0))])
            # except:
            #     bpy.context.scene.meg_max_t = 0


def calc_stc_minmax():
    stc = ColoringMakerPanel.stc
    data_min = mu.min_stc(stc)
    data_max = mu.max_stc(stc)
    factor = -int(np.round(np.log10(data_max)))
    if factor > 3:
        # ColoringMakerPanel.stc = mne.SourceEstimate(data, vertices, stc.tmin + t * stc.tstep, stc.tstep, subject=subject)
        ColoringMakerPanel.stc._data *= np.power(10, factor)
        data_min *= np.power(10, factor)
        data_max *= np.power(10, factor)
    if np.sign(data_max) != np.sign(data_min) and data_min != 0:
        data_minmax = max(map(abs, [data_min, data_max]))
        ColoringMakerPanel.meg_data_min, ColoringMakerPanel.meg_data_max = -data_minmax, data_minmax
    else:
        if data_min >= 0 and data_max >= 0:
            ColoringMakerPanel.meg_data_min, ColoringMakerPanel.meg_data_max = 0, data_max
        else:
            ColoringMakerPanel.meg_data_min, ColoringMakerPanel.meg_data_max = data_min, 0
    return ColoringMakerPanel.meg_data_min, ColoringMakerPanel.meg_data_max


def plot_fmri_file(fmri_template_fname):
    _fmri_files_update(mu.namebase(fmri_template_fname)[:-len('.{hemi}')])
    activity_map_coloring('FMRI')


def _fmri_files_update(fmri_file_name):
    #todo: there are two frmi files list (the other one in fMRI panel)
    user_fol = mu.get_user_fol()
    fname_template = op.join(user_fol, 'fmri', 'fmri_{}_{}.npy'.format(fmri_file_name, '{hemi}'))
    if not mu.both_hemi_files_exist(fname_template):
        fname_template = op.join(user_fol, 'fmri', 'fmri_{}.{}.npy'.format(fmri_file_name, '{hemi}'))
    if not mu.both_hemi_files_exist(fname_template):
        fname_template = op.join(user_fol, 'fmri', 'fmri_{}-{}.npy'.format(fmri_file_name, '{hemi}'))
    if not mu.both_hemi_files_exist(fname_template):
        print('fmri_files_update: {} does not exist!'.format(fname_template))
        ColoringMakerPanel.fMRI['rh'] = None
        ColoringMakerPanel.fMRI['lh'] = None
        return
    for hemi in mu.HEMIS:
        fname = fname_template.format(hemi=hemi)
        ColoringMakerPanel.fMRI[hemi] = np.load(fname)
    fmri_data_maxmin_fname = op.join(mu.get_user_fol(), 'fmri', 'fmri_activity_map_minmax_{}.pkl'.format(
        bpy.context.scene.fmri_files))
    if not op.isfile(fmri_data_maxmin_fname):
        fmri_data_maxmin_fname = op.join(mu.get_user_fol(), 'fmri', '{}_minmax.pkl'.format(
            bpy.context.scene.fmri_files))
    if not op.isfile(fmri_data_maxmin_fname):
        calc_fmri_min_max(fmri_data_maxmin_fname, fname_template)
    data_min, data_max = mu.load(fmri_data_maxmin_fname)
    ColoringMakerPanel.fmri_activity_colors_ratio = 256 / (data_max - data_min)
    ColoringMakerPanel.fmri_activity_data_minmax = (data_min, data_max)
    if not _addon().colorbar_values_are_locked():
        _addon().set_colorbar_max_min(data_max, data_min)
        _addon().set_colorbar_title('fMRI')


def fmri_files_update(self, context):
    _fmri_files_update(bpy.context.scene.fmri_files)


def calc_fmri_min_max(fmri_data_maxmin_fname, fname_template):
    # Remove the RGB columns
    for hemi in mu.HEMIS:
        fname = fname_template.format(hemi=hemi)
        x = np.load(fname)
        if x.ndim > 1 and x.shape[1] == 4:
            x = x[:, 0]
            np.save(fname, x)
        ColoringMakerPanel.fMRI[hemi] = x
    data = np.hstack((ColoringMakerPanel.fMRI[hemi] for hemi in mu.HEMIS))
    data_min, data_max = np.nanmin(data), np.nanmax(data)
    print('fmri_files_update: min: {}, max: {}'.format(data_min, data_max))
    data_minmax = mu.get_max_abs(data_max, data_min)
    if np.sign(data_max) != np.sign(data_min) and data_min != 0:
        data_max, data_min = data_minmax, -data_minmax
    mu.save((data_min, data_max), fmri_data_maxmin_fname)


def electrodes_sources_files_update(self, context):
    ColoringMakerPanel.electrodes_sources_labels_data, ColoringMakerPanel.electrodes_sources_subcortical_data = \
        get_elecctrodes_sources()


def get_elecctrodes_sources():
    labels_fname = op.join(mu.get_user_fol(), 'electrodes', '{}-{}.npz'.format(
        bpy.context.scene.electrodes_sources_files, '{hemi}'))
    subcorticals_fname = labels_fname.replace('labels', 'subcortical').replace('-{hemi}', '')
    electrodes_sources_labels_data = \
        {hemi:np.load(labels_fname.format(hemi=hemi)) for hemi in mu.HEMIS}
    electrodes_sources_subcortical_data = np.load(subcorticals_fname)
    return electrodes_sources_labels_data, electrodes_sources_subcortical_data


def color_electrodes_sources():
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES_SOURCES)
    labels_data = ColoringMakerPanel.electrodes_sources_labels_data
    rh_data, lh_data = labels_data['rh']['data'], labels_data['lh']['data']
    subcorticals = ColoringMakerPanel.electrodes_sources_subcortical_data
    sub_data = subcorticals['data']

    _max = partial(np.percentile, q=97)
    _min = partial(np.percentile, q=3)
    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
        colors_ratio = 256 / (data_max - data_min)
    else:
        data_min = min([_min(sub_data), _min(rh_data), _min(lh_data)])
        data_max = max([_max(sub_data), _max(rh_data), _max(lh_data)])
        data_minmax = max(map(abs, [data_min, data_max]))
        data_min, data_max = -data_minmax, data_minmax
        colors_ratio = 256 / (data_max - data_min)
        _addon().set_colorbar_max_min(data_max, data_min)
    _addon().set_colorbar_title('Electordes-Cortex')
    curr_sub_data = sub_data[:, bpy.context.scene.frame_current, 0]
    subs_colors = calc_colors(curr_sub_data, data_min, colors_ratio)
    # cond_inds = np.where(subcortical_data['conditions'] == bpy.context.scene.conditions_selection)[0]
    # if len(cond_inds) == 0:
    #     print("!!! Can't find the current condition in the data['conditions'] !!!")
    #     return {"FINISHED"}
    clear_subcortical_regions()
    for region, color in zip(subcorticals['names'], subs_colors):
        # print('electrodes source: color {} with {}'.format(region, color))
        color_subcortical_region(region, color)
    for hemi in mu.HEMIS:
        if bpy.data.objects['inflated_{}'.format(hemi)].hide:
            continue
        labels_coloring_hemi(labels_data[hemi], ColoringMakerPanel.faces_verts, hemi, 0,
                             colors_min=data_min, colors_max=data_max)


def color_eeg_helmet():
    fol = mu.get_user_fol()
    data_fname = op.join(fol, 'eeg', 'eeg_data.npy')
    data = np.load(data_fname)
    data = np.diff(data).squeeze()
    lookup = np.load(op.join(fol, 'eeg', 'eeg_faces_verts.npy'))
    threshold = 0
    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
    else:
        data_min, data_max = np.percentile(data, 3), np.percentile(data, 97)
        _addon().set_colorbar_max_min(data_max, data_min, True)
    colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_title('EEG')
    data_t = data[:, bpy.context.scene.frame_current]

    cur_obj = bpy.data.objects['eeg_helmet']
    activity_map_obj_coloring(cur_obj, data_t, lookup, threshold, True, data_min=data_min,
                              colors_ratio=colors_ratio, bigger_or_equall=False)


def color_meg_sensors():
    _addon().show_hide_meg_sensors()
    ColoringMakerPanel.what_is_colored.add(WIC_MEG_SENSORS)
    threshold = bpy.context.scene.coloring_threshold
    data, meta = _addon().load_meg_sensors_data()
    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
    else:
        data_min, data_max = ColoringMakerPanel.meg_sensors_data_minmax
        _addon().set_colorbar_max_min(data_max, data_min)
    colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_title('EEG conditions difference')
    color_objects_homogeneously(data, meta['names'], meta['conditions'], data_min, colors_ratio, threshold)


def color_eeg_sensors():
    _addon().show_hide_eeg()
    ColoringMakerPanel.what_is_colored.add(WIC_EEG)
    threshold = bpy.context.scene.coloring_threshold
    data, meta = _addon().load_eeg_data()
    if _addon().colorbar_values_are_locked():
        data_max, data_min = _addon().get_colorbar_max_min()
    else:
        data_min, data_max = ColoringMakerPanel.eeg_data_minmax
        _addon().set_colorbar_max_min(data_max, data_min)
    colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_title('EEG conditions difference')
    color_objects_homogeneously(data, meta['names'], meta['conditions'], data_min, colors_ratio, threshold)


def color_electrodes_dists():
    bpy.context.scene.show_hide_electrodes = True
    _addon().show_hide_electrodes(True)
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES_DISTS)
    dists = _addon().load_electrodes_dists()
    _, names, conditions = _addon().load_electrodes_data()
    selected_objects = bpy.context.selected_objects
    if not (len(selected_objects) == 1 and selected_objects[0].name in names):
        return

    selected_elec = selected_objects[0].name
    selected_elec_ind = np.where(names == selected_elec)[0]
    data = dists[selected_elec_ind].squeeze()
    data_max = np.max(dists)
    colors_ratio = 256 / data_max
    _addon().set_colorbar_max_min(data_max, 0)
    _addon().set_colorbar_title('Electordes conditions difference')
    _addon().set_colormap('hot')
    color_objects_homogeneously(data, names, conditions, 0, colors_ratio, 0)
    _addon().show_electrodes()


def color_electrodes():
    # mu.set_show_textured_solid(False)
    bpy.context.scene.show_hide_electrodes = True
    _addon().show_hide_electrodes(True)
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES)
    threshold = bpy.context.scene.coloring_threshold
    data, names, conditions = _addon().load_electrodes_data()
    if not _addon().colorbar_values_are_locked():
        norm_percs = (3, 97)  # todo: add to gui
        data_max, data_min = mu.get_data_max_min(data, True, norm_percs=norm_percs, data_per_hemi=False, symmetric=True)
        colors_ratio = 256 / (data_max - data_min)
        _addon().set_colorbar_max_min(data_max, data_min)
    else:
        data_max, data_min = _addon().get_colorbar_max_min()
        colors_ratio = 256 / (data_max - data_min)
    _addon().set_colorbar_title('Electordes conditions difference')
    color_objects_homogeneously(data, names, conditions, data_min, colors_ratio, threshold)
    _addon().show_electrodes()
    # for obj in bpy.data.objects['Deep_electrodes'].children:
    #     bpy.ops.object.editmode_toggle()
    #     bpy.ops.object.editmode_toggle()

    # mu.update()
    # mu.set_show_textured_solid(True)
    # _addon().change_to_rendered_brain()


    # deselect_all()
    # mu.select_hierarchy('Deep_electrodes', False)


def color_electrodes_stim():
    ColoringMakerPanel.what_is_colored.add(WIC_ELECTRODES_STIM)
    threshold = bpy.context.scene.coloring_threshold
    stim_fname = 'stim_electrodes_{}.npz'.format(bpy.context.scene.stim_files.replace(' ', '_'))
    stim_data_fname = op.join(mu.get_user_fol(), 'electrodes', stim_fname)
    data = np.load(stim_data_fname)
    color_objects_homogeneously(data, threshold=threshold)
    _addon().show_electrodes()
    _addon().change_to_rendered_brain()


def color_connections(threshold=None):
    clear_connections()
    _addon().plot_connections(_addon().connections_data(), bpy.context.scene.frame_current, threshold)


def clear_and_recolor():
    color_meg = partial(activity_map_coloring, map_type='MEG')
    color_fmri = partial(activity_map_coloring, map_type='FMRI')
    color_fmri_clusters = partial(activity_map_coloring, map_type='FMRI', clusters=True)

    wic_funcs = {
        WIC_MEG:color_meg,
        WIC_MEG_LABELS:meg_labels_coloring,
        WIC_FMRI:color_fmri,
        WIC_FMRI_CLUSTERS:color_fmri_clusters,
        WIC_ELECTRODES:color_electrodes,
        WIC_ELECTRODES_SOURCES:color_electrodes_sources,
        WIC_ELECTRODES_STIM:color_electrodes_stim,
        WIC_MANUALLY:color_manually,
        WIC_GROUPS:color_groups_manually,
        WIC_VOLUMES:color_volumetric}

    what_is_colored = ColoringMakerPanel.what_is_colored
    clear_colors()
    for wic in what_is_colored:
        wic_funcs[wic]()


def get_condditions_from_labels_fcurves():
    conditions = []
    parent_obj = bpy.data.objects.get('Cortex-lh')
    if parent_obj:
        label_obj = parent_obj.children[0]
        fcurves_names = mu.get_fcurves_names(label_obj)
        conditions = [fc_name.split('_')[-1] for fc_name in fcurves_names]
    return conditions


class ColorEEGHelmet(bpy.types.Operator):
    bl_idname = "mmvt.eeg_helmet"
    bl_label = "mmvt eeg helmet"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_eeg_helmet()
        return {"FINISHED"}


class ColorConnections(bpy.types.Operator):
    bl_idname = "mmvt.connections_color"
    bl_label = "mmvt connections color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_connections()
        return {"FINISHED"}


class ColorStaticConnectionsDegree(bpy.types.Operator):
    bl_idname = "mmvt.connectivity_degree"
    bl_label = "mmvt connectivity_degree"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_connectivity_degree()
        return {"FINISHED"}


class ColorConnectionsLabelsAvg(bpy.types.Operator):
    bl_idname = "mmvt.connections_labels_avg"
    bl_label = "mmvt connections labels avg"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_connections_labels_avg()
        return {"FINISHED"}


class ColorMEGSensors(bpy.types.Operator):
    bl_idname = "mmvt.color_meg_sensors"
    bl_label = "mmvt color_meg_sensors"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_meg_sensors()
        return {"FINISHED"}


class ColorEEGSensors(bpy.types.Operator):
    bl_idname = "mmvt.color_eeg_sensors"
    bl_label = "mmvt color_eeg_sensors"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_eeg_sensors()
        return {"FINISHED"}


class ColorElectrodes(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color"
    bl_label = "mmvt electrodes color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes()
        return {"FINISHED"}


class ColorElectrodesDists(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_dists_color"
    bl_label = "mmvt electrodes dists color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes_dists()
        return {"FINISHED"}


class ColorElectrodesLabels(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color_labels"
    bl_label = "mmvt electrodes color labels"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes_sources()
        return {"FINISHED"}


class ColorElectrodesStim(bpy.types.Operator):
    bl_idname = "mmvt.electrodes_color_stim"
    bl_label = "mmvt electrodes color stim"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_electrodes_stim()
        return {"FINISHED"}


class ColorManually(bpy.types.Operator):
    bl_idname = "mmvt.man_color"
    bl_label = "mmvt man color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_manually()
        return {"FINISHED"}


class ColorVol(bpy.types.Operator):
    bl_idname = "mmvt.vol_color"
    bl_label = "mmvt vol color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_volumetric()
        return {"FINISHED"}


class ColorGroupsManually(bpy.types.Operator):
    bl_idname = "mmvt.man_groups_color"
    bl_label = "mmvt man groups color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_groups_manually()
        return {"FINISHED"}


class ColorfMRIDynamics(bpy.types.Operator):
    bl_idname = "mmvt.fmri_dynamics_color"
    bl_label = "mmvt fmri dynamics color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('FMRI_DYNAMICS')
        return {"FINISHED"}


class ColorContours(bpy.types.Operator):
    bl_idname = "mmvt.color_contours"
    bl_label = "mmvt color contours"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        color_contours()
        return {"FINISHED"}


class PrevLabelConture(bpy.types.Operator):
    bl_idname = "mmvt.labels_contours_prev"
    bl_label = "mmvt labels contours prev"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        all_labels = np.concatenate((ColoringMakerPanel.labels['rh'], ColoringMakerPanel.labels['lh']))
        if bpy.context.scene.labels_contures == 'all labels':
            bpy.context.scene.labels_contures = all_labels[-1]
        else:
            label_ind = np.where(all_labels == bpy.context.scene.labels_contures)[0][0]
            bpy.context.scene.labels_contures = all_labels[label_ind - 1] if label_ind > 0 else all_labels[-1]
        return {"FINISHED"}


class NextLabelConture(bpy.types.Operator):
    bl_idname = "mmvt.labels_contours_next"
    bl_label = "mmvt labels contours next"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        all_labels = np.concatenate((ColoringMakerPanel.labels['rh'], ColoringMakerPanel.labels['lh']))
        if bpy.context.scene.labels_contures == 'all labels':
            bpy.context.scene.labels_contures = all_labels[0]
        else:
            label_ind = np.where(all_labels == bpy.context.scene.labels_contures)[0][0]
            bpy.context.scene.labels_contures = all_labels[label_ind + 1] \
                if label_ind < len(all_labels) else all_labels[0]
        return {"FINISHED"}


class ColorMeg(bpy.types.Operator):
    bl_idname = "mmvt.meg_color"
    bl_label = "mmvt meg color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        if ColoringMakerPanel.stc_file_chosen:
            plot_stc(ColoringMakerPanel.stc, bpy.context.scene.frame_current,
                     threshold=bpy.context.scene.coloring_threshold, save_image=False)
        elif ColoringMakerPanel.activity_map_chosen:
            activity_map_coloring('MEG')
        else:
            print('ColorMeg: Both stc_file_chosen and activity_map_chosen are False!')
        return {"FINISHED"}


class ColorMegMax(bpy.types.Operator):
    bl_idname = "mmvt.meg_max_color"
    bl_label = "mmvt meg max color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        if ColoringMakerPanel.stc_file_chosen:
            max_vert, bpy.context.scene.frame_current = ColoringMakerPanel.stc.get_peak(
                time_as_index=True, vert_as_index=True, mode=bpy.context.scene.meg_peak_mode)
            print(max_vert, bpy.context.scene.frame_current)
            plot_stc(ColoringMakerPanel.stc, bpy.context.scene.frame_current,
                     threshold=bpy.context.scene.coloring_threshold, save_image=False)
        elif ColoringMakerPanel.activity_map_chosen:
            #todo: implement
            pass
            # activity_map_coloring('MEG')
        else:
            print('ColorMegMax: Both stc_file_chosen and activity_map_chosen are False!')
        return {"FINISHED"}

class ColorMegLabels(bpy.types.Operator):
    bl_idname = "mmvt.meg_labels_color"
    bl_label = "mmvt meg labels color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        meg_labels_coloring()
        return {"FINISHED"}


class ColorfMRI(bpy.types.Operator):
    bl_idname = "mmvt.fmri_color"
    bl_label = "mmvt fmri color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('FMRI')
        return {"FINISHED"}


class ColorfMRILabels(bpy.types.Operator):
    bl_idname = "mmvt.fmri_labels_color"
    bl_label = "mmvt fmri labels_color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        fmri_labels_coloring()
        return {"FINISHED"}


class ColorClustersFmri(bpy.types.Operator):
    bl_idname = "mmvt.fmri_clusters_color"
    bl_label = "mmvt fmri clusters color"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        activity_map_coloring('FMRI', clusters=True)
        return {"FINISHED"}


class ClearColors(bpy.types.Operator):
    bl_idname = "mmvt.colors_clear"
    bl_label = "mmvt colors clear"
    bl_options = {"UNDO"}

    @staticmethod
    def invoke(self, context, event=None):
        clear_colors()
        return {"FINISHED"}


class ChooseLabelFile(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = "mmvt.plot_label_file"
    bl_label = "Plot label file"

    filename_ext = '.label'
    filter_glob = bpy.props.StringProperty(default='*.label', options={'HIDDEN'}, maxlen=255)

    def execute(self, context):
        label_fname = self.filepath
        plot_label(label_fname)
        return {'FINISHED'}


def plot_label(label, color=''):
    if isinstance(label, str):
        label = mu.read_label_file(label)
    else:
        try:
            _, _, _ = label.name, label.vertices, label.pos
        except:
            raise Exception('plot_label: label can be label fname or label object!')
    # hemi_obj_vertices = bpy.data.objects[label.hemi].data.vertices
    # label_pos = np.array([hemi_obj_vertices[v].co for v in label.vertices])
    # bpy.context.scene.cursor_location = np.mean(label_pos, 0) / 10
    # print('new label center of mass: {}'.format(bpy.context.scene.cursor_location * 10))

    color = list(bpy.context.scene.labels_color) if color == '' else color
    ColoringMakerPanel.labels_plotted.append((label, color))
    hemi_verts_num = {hemi: ColoringMakerPanel.faces_verts[hemi].shape[0] for hemi in mu.HEMIS}
    data = {hemi: np.zeros((hemi_verts_num[hemi], 4)) for hemi in mu.HEMIS}
    for label, color in ColoringMakerPanel.labels_plotted:
        data[label.hemi][label.vertices] = [1, *color]
    for hemi in mu.HEMIS:
        color_hemi_data(hemi, data[hemi], threshold=0.5)
    _addon().show_activity()


def plot_labels(labels_names, colors, atlas):
    atlas_labels = mu.read_labels_from_annots(mu.get_user(), mu.get_subjects_dir(), atlas, hemi='both')
    org_delim, org_pos, label, label_hemi = mu.get_hemi_delim_and_pos(atlas_labels[0].name)
    labels_names_fix = []
    for label_name in labels_names:
        delim, pos, label, label_hemi = mu.get_hemi_delim_and_pos(label_name)
        label_fix = mu.build_label_name(org_delim, org_pos, label, label_hemi)
        labels_names_fix.append(label_fix)
    labels = [l for l in atlas_labels if l.name in labels_names_fix]
    labels.sort(key=lambda x: labels_names_fix.index(x.name))
    # todo: check if bpy.context.scene.color_rois_homogeneously
    for label, color in zip(labels, colors):
        plot_label(label, color)


def clear_colors():
    clear_cortex()
    clear_subcortical_fmri_activity()
    for root in ['Subcortical_meg_activity_map', 'Deep_electrodes', 'EEG_sensors', 'MEG_sensors']:
        clear_colors_from_parent_childrens(root)
    clear_connections()
    ColoringMakerPanel.what_is_colored = set()
    ColoringMakerPanel.labels_plotted = []


def clear_connections():
    vertices_obj = bpy.data.objects.get('connections_vertices')
    if vertices_obj:
        if any([obj.hide for obj in vertices_obj.children]):
            _addon().plot_connections(_addon().connections_data(), bpy.context.scene.frame_current, 0)
            _addon().filter_nodes(False)
            _addon().filter_nodes(True)


def get_fMRI_activity(hemi, clusters=False):
    if clusters:
        f = [c for c in ColoringMakerPanel.fMRI_clusters if c['hemi'] == hemi]
    else:
        f = ColoringMakerPanel.fMRI[hemi]
    return f
    # return ColoringMakerPanel.fMRI_clusters[hemi] if clusters else ColoringMakerPanel.fMRI[hemi]


def get_faces_verts():
    return ColoringMakerPanel.faces_verts


def read_groups_labels(colors):
    groups_fname = op.join(mu.get_parent_fol(mu.get_user_fol()), '{}_groups.csv'.format(bpy.context.scene.atlas))
    if not op.isfile(groups_fname):
        return {}
    groups = defaultdict(list) # OrderedDict() # defaultdict(list)
    color_ind = 0
    for line in mu.csv_file_reader(groups_fname):
        group_name = line[0]
        group_color = line[1]
        labels = line[2:]
        if group_name[0] == '#':
            continue
        groups[group_name] = []
        for label in labels:
            # group_color = cu.name_to_rgb(colors[color_ind])
            groups[group_name].append(dict(name=label, color=cu.name_to_rgb(group_color)))
            color_ind += 1
    order_groups = OrderedDict()
    groups_names = sorted(list(groups.keys()))
    for group_name in groups_names:
        order_groups[group_name] = groups[group_name]
    return order_groups


def draw(self, context):
    layout = self.layout
    user_fol = mu.get_user_fol()
    atlas = bpy.context.scene.atlas
    faces_verts_exist = mu.hemi_files_exists(op.join(user_fol, 'faces_verts_{hemi}.npy'))
    fmri_files = glob.glob(op.join(user_fol, 'fmri', 'fmri_*_lh.npy'))  # mu.hemi_files_exists(op.join(user_fol, 'fmri_{hemi}.npy'))
    # fmri_clusters_files_exist = mu.hemi_files_exists(op.join(user_fol, 'fmri', 'fmri_clusters_{hemi}.npy'))
    meg_ext_meth = bpy.context.scene.meg_labels_extract_method
    meg_labels_data_exist = mu.hemi_files_exists(op.join(user_fol, 'meg', 'labels_data_{}_{}_{}.npz'.format(
        atlas, meg_ext_meth, '{hemi}')))
    meg_labels_data_minmax_exist = op.isfile(
        op.join(user_fol, 'meg', 'meg_labels_{}_{}_minmax.npz'.format(atlas, meg_ext_meth)))
    # fmri_labels_data_exist = mu.hemi_files_exists(
    #     op.join(user_fol, 'fmri', 'labels_data_{}_{}.npz'.format(atlas, '{hemi}')))
    # fmri_labels_data_minmax_exist = op.isfile(
    #     op.join(user_fol, 'meg', 'meg_labels_{}_minmax.npz'.format(atlas)))
    bip = 'bipolar_' if bpy.context.scene.bipolar else ''
    electrodes_files_exist = \
        op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_{}data.npz'.format(bip))) or \
        op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_{}data.npy'.format(bip)))
    electrodes_dists_exist = op.isfile(op.join(mu.get_user_fol(), 'electrodes', 'electrodes_dists.npy'))
    electrodes_stim_files_exist = len(glob.glob(op.join(
        mu.get_user_fol(), 'electrodes', 'stim_electrodes_*.npz'))) > 0
    electrodes_labels_files_exist = len(glob.glob(op.join(
        mu.get_user_fol(), 'electrodes', '*_labels_*.npz'))) > 0 and \
                                    len(glob.glob(op.join(mu.get_user_fol(), 'electrodes', '*_subcortical_*.npz'))) > 0
    manually_color_files_exist = len(glob.glob(op.join(user_fol, 'coloring', '*.csv'))) > 0
    static_connectivity_exist = len(glob.glob(op.join(user_fol, 'connectivity', '*_static_*.npy'))) > 0
    # manually_groups_file_exist = op.isfile(op.join(mu.get_parent_fol(user_fol),
    #                                                '{}_groups.csv'.format(bpy.context.scene.atlas)))
    if _addon() is None:
        connections_files_exit = False
    else:
        connections_files_exit = _addon().connections_exist() and not _addon().connections_data() is None
    # volumetric_coloring_files_exist = len(glob.glob(op.join(user_fol, 'coloring', 'volumetric', '*.csv')))
    layout.prop(context.scene, 'coloring_threshold', text="Threshold")
    # layout.prop(context.scene, 'coloring_both_pial_and_inflated', text="Both pial & inflated")
    layout.prop(context.scene, 'color_rois_homogeneously', text="Color ROIs homogeneously")

    if faces_verts_exist:
        meg_current_activity_data_exist = mu.hemi_files_exists(
            op.join(user_fol, 'activity_map_{hemi}', 't{}.npy'.format(bpy.context.scene.frame_current)))
        if ColoringMakerPanel.meg_activity_data_exist and meg_current_activity_data_exist or \
                ColoringMakerPanel.stc_file_exist:
            col = layout.box().column()
            # mu.add_box_line(col, '', 'MEG', 0.4)
            col.prop(context.scene, 'meg_files', '')
            # col.label(text='T max: {}'.format(bpy.context.scene.meg_max_t))
            col.operator(ColorMeg.bl_idname, text="Plot MEG ", icon='POTATO')
            col.operator(ColorMegMax.bl_idname, text="Plot MEG peak", icon='POTATO')
            col.prop(context.scene, 'meg_peak_mode', '')
            if op.isfile(op.join(mu.get_user_fol(), 'subcortical_meg_activity.npz')):
                col.prop(context.scene, 'coloring_meg_subcorticals', text="Plot also subcorticals")
        if meg_labels_data_exist and meg_labels_data_minmax_exist:
            col = layout.box().column()
            # col.label('MEG labels')
            col.prop(context.scene, 'meg_labels_coloring_type', '')
            col.operator(ColorMegLabels.bl_idname, text="Plot MEG Labels ", icon='POTATO')
        if len(fmri_files) > 0 or ColoringMakerPanel.fmri_activity_map_exist or ColoringMakerPanel.fmri_labels_exist:
            col = layout.box().column()
            # col.label('fMRI')
            if len(fmri_files) > 0:
                col.prop(context.scene, "fmri_files", text="")
                col.operator(ColorfMRI.bl_idname, text="Plot fMRI file", icon='POTATO')
            if ColoringMakerPanel.fmri_activity_map_exist:
                col.operator(ColorfMRIDynamics.bl_idname, text="Plot fMRI Dynamics", icon='POTATO')
            if ColoringMakerPanel.fmri_labels_exist:
                col.operator(ColorfMRILabels.bl_idname, text="Plot fMRI Labels", icon='POTATO')
        if ColoringMakerPanel.contours_coloring_exist:
            col = layout.box().column()
            col.prop(context.scene, 'contours_coloring', '')
            col.operator(ColorContours.bl_idname, text="Plot Contours", icon='POTATO')
            row = col.row(align=True)
            row.operator(PrevLabelConture.bl_idname, text="", icon='PREV_KEYFRAME')
            row.prop(context.scene, 'labels_contures', '')
            row.operator(NextLabelConture.bl_idname, text="", icon='NEXT_KEYFRAME')
        if manually_color_files_exist:
            col = layout.box().column()
            # col.label('Manual coloring files')
            col.prop(context.scene, "coloring_files", text="")
            col.operator(ColorManually.bl_idname, text="Color Manually", icon='POTATO')
        row = layout.row(align=True)
        row.operator(ChooseLabelFile.bl_idname, text="plot a label", icon='GAME').filepath = op.join(
            mu.get_user_fol(), '*.label')
        row.prop(context.scene, 'labels_color', text='')
        if len(ColoringMakerPanel.labels_plotted) > 0:
            box = layout.box()
            col = box.column()
            for label, color in ColoringMakerPanel.labels_plotted:
                mu.add_box_line(col, label.name, percentage=1)

            # if manually_groups_file_exist:
        #     col = layout.box().column()
            # col.label('Groups')
            # col.prop(context.scene, 'labels_groups', text="")
            # col.operator(ColorGroupsManually.bl_idname, text="Color Groups", icon='POTATO')
            # if volumetric_coloring_files_exist:
            #     layout.prop(context.scene, "vol_coloring_files", text="")
            #     layout.operator(ColorVol.bl_idname, text="Color Volumes", icon='POTATO')

    if ColoringMakerPanel.meg_sensors_exist:
        col = layout.box().column()
        col.operator(ColorMEGSensors.bl_idname, text="Plot MEG sensors", icon='POTATO')

    if ColoringMakerPanel.eeg_exist:
        col = layout.box().column()
        col.operator(ColorEEGSensors.bl_idname, text="Plot EEG sensors", icon='POTATO')
        # if not bpy.data.objects.get('eeg_helmet', None) is None:
        #     layout.operator(ColorEEGHelmet.bl_idname, text="Plot EEG Helmet", icon='POTATO')

    if electrodes_files_exist:
        col = layout.box().column()
        col.operator(ColorElectrodes.bl_idname, text="Plot Electrodes", icon='POTATO')
        if electrodes_dists_exist:
            col.operator(ColorElectrodesDists.bl_idname, text="Plot Electrodes Dists", icon='POTATO')
        if electrodes_labels_files_exist:
            col.prop(context.scene, "electrodes_sources_files", text="")
            col.operator(ColorElectrodesLabels.bl_idname, text="Plot Electrodes Sources", icon='POTATO')
        if electrodes_stim_files_exist:
            col.operator(ColorElectrodesStim.bl_idname, text="Plot Electrodes Stimulation", icon='POTATO')
    if connections_files_exit:
        col = layout.box().column()
        col.operator(ColorConnections.bl_idname, text="Plot Connections", icon='POTATO')
        col.prop(context.scene, 'hide_connection_under_threshold', text='Hide connections under threshold')
        if ColoringMakerPanel.conn_labels_avg_files_exit:
            col.prop(context.scene, 'conn_labels_avg_files', text='')
            col.operator(ColorConnectionsLabelsAvg.bl_idname, text="Plot Connections Labels Avg", icon='POTATO')
    if static_connectivity_exist:
        col = layout.box().column()
        col.prop(context.scene, 'static_conn_files', text='')
        col.prop(context.scene, 'connectivity_degree_threshold', text="Threshold")
        col.prop(context.scene, 'connectivity_degree_threshold_use_abs', text="Use connectivity absolute value")
        col.prop(context.scene, 'connectivity_degree_save_image', text="Save an image each update")
        col.operator(ColorStaticConnectionsDegree.bl_idname, text="Plot Connectivity Degree", icon='POTATO')

    layout.operator(ClearColors.bl_idname, text="Clear", icon='PANEL_CLOSE')


bpy.types.Scene.hide_connection_under_threshold = bpy.props.BoolProperty(
    default=True, description="Hide connections under threshold")
bpy.types.Scene.meg_activitiy_type = bpy.props.EnumProperty(
    items=[('diff', 'Conditions difference', '', 0)], description="MEG activity type")
bpy.types.Scene.meg_peak_mode = bpy.props.EnumProperty(
    items=[('abs', 'Absolute values', '', 0), ('pos', 'Only positive', '', 1), ('neg', 'only negative', '', 2)])
bpy.types.Scene.meg_labels_coloring_type = bpy.props.EnumProperty(items=[], description="MEG labels coloring type")
bpy.types.Scene.coloring_fmri = bpy.props.BoolProperty(default=True, description="Plot FMRI")
bpy.types.Scene.coloring_electrodes = bpy.props.BoolProperty(default=False, description="Plot Deep electrodes")
bpy.types.Scene.coloring_threshold = bpy.props.FloatProperty(default=0.5, min=0, description="")
bpy.types.Scene.fmri_files = bpy.props.EnumProperty(items=[('', '', '', 0)], description="fMRI files")
bpy.types.Scene.stc_files = bpy.props.EnumProperty(items=[('', '', '', 0)], description="STC files")
bpy.types.Scene.meg_max_t = bpy.props.IntProperty(default=0, min=0, description="MEG max t")
bpy.types.Scene.electrodes_sources_files = bpy.props.EnumProperty(items=[], description="electrodes sources files")
bpy.types.Scene.coloring_files = bpy.props.EnumProperty(items=[], description="Coloring files")
bpy.types.Scene.vol_coloring_files = bpy.props.EnumProperty(items=[], description="Coloring volumetric files")
# bpy.types.Scene.coloring_both_pial_and_inflated = bpy.props.BoolProperty(default=False, description="")
bpy.types.Scene.color_rois_homogeneously = bpy.props.BoolProperty(default=True, description="")
bpy.types.Scene.coloring_meg_subcorticals = bpy.props.BoolProperty(default=False, description="")
bpy.types.Scene.conn_labels_avg_files = bpy.props.EnumProperty(items=[], description="Connectivity labels avg")
bpy.types.Scene.contours_coloring = bpy.props.EnumProperty(items=[], description="labels contours coloring")
bpy.types.Scene.labels_contures = bpy.props.EnumProperty(items=[])
bpy.types.Scene.labels_color = bpy.props.FloatVectorProperty(
    name="labels_color", subtype='COLOR', default=(0, 0.5, 0), min=0.0, max=1.0, description="color picker")
bpy.types.Scene.static_conn_files = bpy.props.EnumProperty(items=[])
bpy.types.Scene.connectivity_degree_threshold = bpy.props.FloatProperty(
    default=0.7, min=0, max=1, description="", update=update_connectivity_degree_threshold)
bpy.types.Scene.connectivity_degree_threshold_use_abs = bpy.props.BoolProperty(default=False, description="")
bpy.types.Scene.connectivity_degree_save_image = bpy.props.BoolProperty(default=False, description="")


class ColoringMakerPanel(bpy.types.Panel):
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_context = "objectmode"
    bl_category = "mmvt"
    bl_label = "Activity Maps"
    addon = None
    init = False
    fMRI = {}
    fMRI_clusters = {}
    labels_vertices = {}
    labels = dict(rh=[], lh=[])
    electrodes_sources_labels_data = None
    electrodes_sources_subcortical_data = None
    what_is_colored = set()
    fmri_activity_data_minmax, fmri_activity_colors_ratio = None, None
    meg_activity_data_minmax, meg_activity_colors_ratio = None, None
    meg_data_min, meg_data_max = 0, 0
    eeg_data_minmax, eeg_colors_ratio = None, None
    meg_sensors_data_minmax, meg_sensors_colors_ratio = None, None
    labels_plotted = []
    static_conn = None
    connectivity_labels = []

    stc = None
    stc_file_chosen = False
    activity_map_chosen = False
    stc_file_exist = False
    meg_activity_data_exist = False
    fmri_labels_exist = False
    fmri_subcorticals_mean_exist = False
    fmri_activity_map_exist = False
    eeg_exist = False
    meg_sensors_exist = False
    conn_labels_avg_files_exit = False
    contours_coloring_exist = False
    stc = None

    activity_map_coloring = activity_map_coloring

    def draw(self, context):
        draw(self, context)


def init(addon):
    ColoringMakerPanel.addon = addon
    ColoringMakerPanel.faces_verts = None
    ColoringMakerPanel.subs_faces_verts, ColoringMakerPanel.subs_verts = None, None

    register()
    init_meg_activity_map()
    init_fmri_activity_map()
    init_meg_labels_coloring_type()
    init_fmri_files()
    init_fmri_labels()
    init_electrodes_sources()
    init_coloring_files()
    init_labels_groups()
    init_labels_vertices()
    init_eeg_sensors()
    init_meg_sensors()
    init_connectivity_labels_avg()
    init_contours_coloring()
    init_static_conn()

    ColoringMakerPanel.faces_verts = load_faces_verts()
    bpy.context.scene.coloring_meg_subcorticals = False
    bpy.context.scene.meg_peak_mode = 'abs'
    ColoringMakerPanel.init = True
    for hemi in ['lh', 'rh']:
        mesh = bpy.data.objects['inflated_{}'.format(hemi)].data
        if mesh.vertex_colors.get('Col') is None:
            mesh.vertex_colors.new('Col')


def init_labels_vertices():
    user_fol = mu.get_user_fol()
    labels_vertices_fname = op.join(user_fol, 'labels_vertices_{}.pkl'.format(bpy.context.scene.atlas))
    if op.isfile(labels_vertices_fname):
        labels_names, labels_vertices = mu.load(labels_vertices_fname)
        ColoringMakerPanel.labels_vertices = dict(labels_names=labels_names, labels_vertices=labels_vertices)
        ColoringMakerPanel.max_labels_vertices_num = {}
    else:
        print("Can't load Activity maps panel without the file {}!".format(labels_vertices_fname))
        #todo: Disable this functionalty


def init_meg_activity_map():
    user_fol = mu.get_user_fol()
    list_items = []
    activity_types = [mu.namebase(f)[len('activity_map_'):-2] for f in glob.glob(op.join(user_fol, 'activity_map_*rh'))]
    for activity_type in activity_types:
        if activity_type != '':
            activity_type = activity_type[:-1]
        meg_files_exist = len(glob.glob(op.join(user_fol, 'activity_map_{}rh'.format(activity_type), 't*.npy'))) > 0 and \
                          len(glob.glob(op.join(user_fol, 'activity_map_{}lh'.format(activity_type), 't*.npy'))) > 0
        meg_data_maxmin_fname = op.join(mu.get_user_fol(), 'meg_activity_map_{}minmax.pkl'.format(activity_type))
        if meg_files_exist and op.isfile(meg_data_maxmin_fname):
            data_min, data_max = mu.load(meg_data_maxmin_fname)
            ColoringMakerPanel.meg_activity_colors_ratio = 256 / (data_max - data_min)
            ColoringMakerPanel.meg_activity_data_minmax = (data_min, data_max)
            print('data meg: {}-{}'.format(data_min, data_max))
            if not _addon().colorbar_values_are_locked():
                _addon().set_colorbar_max_min(data_max, data_min, True)
            _addon().set_colorbar_title('MEG')
            ColoringMakerPanel.meg_activity_data_exist = True
            if activity_type == '':
                activity_type = 'conditions diff'
            list_items.append((activity_type, activity_type, '', len(list_items)))
    if MNE_EXIST:
        list_items = create_stc_files_list(list_items)
    else:
        print('No MNE installed in Blender. Run python -m src.setup -f install_blender_reqs')
    if len(list_items) > 0:
        bpy.types.Scene.meg_files = bpy.props.EnumProperty(
            items=list_items, description="MEG files", update=meg_files_update)
        bpy.context.scene.meg_files = list_items[0][0]


def create_stc_files_list(list_items=[]):
    user_fol = mu.get_user_fol()
    stcs_files = glob.glob(op.join(user_fol, 'meg', '*.stc'))
    stc_files_dic = defaultdict(list)
    for stc_file in stcs_files:
        _, _, label, hemi = mu.get_hemi_delim_and_pos(mu.namebase(stc_file))
        stc_files_dic[label].append(hemi)
    stc_names = [label for label, hemis in stc_files_dic.items() if len(hemis) == 2]
    if len(stc_names) > 0:
        ColoringMakerPanel.stc_file_exist = True
        list_items.extend([(c, c, '', ind + len(list_items)) for ind, c in enumerate(stc_names)])
    return list_items


def init_fmri_activity_map():
    user_fol = mu.get_user_fol()
    fmri_files_exist = mu.hemi_files_exists(op.join(user_fol, 'fmri', 'activity_map_{hemi}', 't0.npy'))
    fmri_data_maxmin_fname = op.join(user_fol, 'fmri', 'activity_map_minmax.npy')
    if fmri_files_exist and op.isfile(fmri_data_maxmin_fname):
        ColoringMakerPanel.fmri_activity_map_exist = True
        data_min, data_max = np.load(fmri_data_maxmin_fname)
        ColoringMakerPanel.fmri_activity_colors_ratio = 256 / (data_max - data_min)
        ColoringMakerPanel.fmri_activity_data_minmax = (data_min, data_max)
        if not _addon().colorbar_values_are_locked():
            _addon().set_colorbar_max_min(data_max, data_min, True)
        _addon().set_colorbar_title('fMRI')


def init_meg_sensors():
    user_fol = mu.get_user_fol()
    data_fname = op.join(user_fol, 'meg', 'meg_sensors_evoked_data.npy')
    meta_data_fname = op.join(user_fol, 'meg', 'meg_sensors_evoked_data_meta.npz')
    data_minmax_fname = op.join(user_fol, 'meg', 'meg_sensors_evoked_minmax.npy')
    if all([op.isfile(f) for f in [data_fname, meta_data_fname, data_minmax_fname]]):
        ColoringMakerPanel.meg_sensors_exist = True
        data_min, data_max = np.load(data_minmax_fname)
        ColoringMakerPanel.meg_sensors_colors_ratio = 256 / (data_max - data_min)
        ColoringMakerPanel.meg_sensors_data_minmax = (data_min, data_max)


def init_eeg_sensors():
    user_fol = mu.get_user_fol()
    data_fname = op.join(user_fol, 'eeg', 'eeg_data.npy')
    meta_data_fname = op.join(user_fol, 'eeg', 'eeg_data_meta.npz')
    data_minmax_fname = op.join(user_fol, 'eeg', 'eeg_data_minmax.npy')
    if all([op.isfile(f) for f in [data_fname, meta_data_fname, data_minmax_fname]]):
        ColoringMakerPanel.eeg_exist = True
        data_min, data_max = np.load(data_minmax_fname)
        ColoringMakerPanel.eeg_colors_ratio = 256 / (data_max - data_min)
        ColoringMakerPanel.eeg_data_minmax = (data_min, data_max)


def init_contours_coloring():
    user_fol = mu.get_user_fol()
    contours_files = glob.glob(op.join(user_fol, '*contours_lh.npz'))
    if len(contours_files) > 0:
        ColoringMakerPanel.contours_coloring_exist = True
        files_names = [mu.namebase(fname)[:-len('_contours_lh')] for fname in contours_files]
        items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.contours_coloring = bpy.props.EnumProperty(items=items, update=contours_coloring_update)
        bpy.context.scene.contours_coloring = files_names[0]


def init_meg_labels_coloring_type():
    user_fol = mu.get_user_fol()
    atlas = bpy.context.scene.atlas
    conditions = get_condditions_from_labels_fcurves()
    em = bpy.context.scene.meg_labels_extract_method
    meg_labels_data_exist = mu.hemi_files_exists(
        op.join(user_fol, 'meg', 'labels_data_{}_{}_{}.npz'.format(atlas, em, '{hemi}')))
    meg_labels_data_minmax_exist = op.isfile(
        op.join(user_fol, 'meg', 'meg_labels_{}_{}_minmax.npz'.format(atlas, em)))
    if len(conditions) > 0 and meg_labels_data_exist and meg_labels_data_minmax_exist:
        items = [('diff', 'Conditions differece', '', 0)]
        items.extend([(cond, cond, '', ind + 1) for ind, cond in enumerate(conditions)])
        bpy.types.Scene.meg_labels_coloring_type = bpy.props.EnumProperty(
            items=items, description="meg_labels_coloring_type")
        bpy.context.scene.meg_labels_coloring_type = 'diff'


def init_fmri_labels():
    user_fol = mu.get_user_fol()
    atlas = bpy.context.scene.atlas
    em = bpy.context.scene.fmri_labels_extract_method
    fmri_labels_data_exist = mu.hemi_files_exists(
        op.join(user_fol, 'fmri', 'labels_data_{}_{}_{}.npz'.format(atlas, em, '{hemi}')))
    fmri_labels_data_minmax_exist = op.isfile(
        op.join(user_fol, 'fmri', 'labels_data_{}_{}_minmax.pkl'.format(atlas, em)))
    ColoringMakerPanel.fmri_labels_exist = fmri_labels_data_exist and fmri_labels_data_minmax_exist
    ColoringMakerPanel.fmri_subcorticals_mean_exist = op.isfile(
        op.join(user_fol, 'fmri', 'subcorticals_{}.npz'.format(em)))
    if ColoringMakerPanel.subs_faces_verts is None or ColoringMakerPanel.subs_verts is None:
        ColoringMakerPanel.subs_faces_verts, ColoringMakerPanel.subs_verts = load_subs_faces_verts()


def init_fmri_files():
    user_fol = mu.get_user_fol()
    fmri_files = glob.glob(op.join(user_fol, 'fmri', 'fmri_*lh.npy'))
    if len(fmri_files) > 0:
        files_names = [mu.namebase(fname)[5:-3] for fname in fmri_files]
        clusters_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.fmri_files = bpy.props.EnumProperty(
            items=clusters_items, description="fMRI files", update=fmri_files_update)
        bpy.context.scene.fmri_files = files_names[0]


def init_static_conn():
    user_fol = mu.get_user_fol()
    conn_labels_names_fname = op.join(mu.get_user_fol(), 'connectivity', 'labels_names.npy')
    if op.isfile(conn_labels_names_fname):
        ColoringMakerPanel.connectivity_labels = np.load(conn_labels_names_fname)
    static_conn_files = glob.glob(op.join(user_fol, 'connectivity', '*_static_*.npy'))
    if len(static_conn_files) > 0:
        files_names = [mu.namebase(fname) for fname in static_conn_files]
        files_names = [name for name in files_names if 'backup' not in name]
        items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.static_conn_files = bpy.props.EnumProperty(
            items=items, description="static conn files", update=static_conn_files_update)
        bpy.context.scene.static_conn_files = files_names[0]


def init_electrodes_sources():
    user_fol = mu.get_user_fol()
    electrodes_source_files = glob.glob(op.join(user_fol, 'electrodes', '*_labels_*-rh.npz'))
    if len(electrodes_source_files) > 0:
        files_names = [mu.namebase(fname)[:-len('-rh')] for fname in electrodes_source_files]
        items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.electrodes_sources_files = bpy.props.EnumProperty(
            items=items, description="electrodes sources", update=electrodes_sources_files_update)
        bpy.context.scene.electrodes_sources_files = files_names[0]


def init_coloring_files():
    user_fol = mu.get_user_fol()
    mu.make_dir(op.join(user_fol, 'coloring'))
    manually_color_files = glob.glob(op.join(user_fol, 'coloring', '*.csv'))
    if len(manually_color_files) > 0:
        files_names = [mu.namebase(fname) for fname in manually_color_files]
        coloring_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.coloring_files = bpy.props.EnumProperty(items=coloring_items, description="Coloring files")
        bpy.context.scene.coloring_files = files_names[0]


def init_colume_coloring_files():
    user_fol = mu.get_user_fol()
    vol_color_files = glob.glob(op.join(user_fol, 'coloring', 'volumetric', '*.csv'))
    if len(vol_color_files) > 0:
        files_names = [mu.namebase(fname) for fname in vol_color_files]
        coloring_items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.vol_coloring_files = bpy.props.EnumProperty(
            items=coloring_items, description="Volumetric Coloring files")
        bpy.context.scene.vol_coloring_files = files_names[0]


def init_labels_groups():
    from random import shuffle
    ColoringMakerPanel.colors = list(set(list(cu.NAMES_TO_HEX.keys())) - set(['black']))
    shuffle(ColoringMakerPanel.colors)
    ColoringMakerPanel.labels_groups = read_groups_labels(ColoringMakerPanel.colors)
    if len(ColoringMakerPanel.labels_groups) > 0:
        groups_items = [(gr, gr, '', ind) for ind, gr in enumerate(list(ColoringMakerPanel.labels_groups.keys()))]
        bpy.types.Scene.labels_groups = bpy.props.EnumProperty(
            items=groups_items, description="Groups")


def init_connectivity_labels_avg():
    user_fol = mu.get_user_fol()
    conn_labels_avg_files = glob.glob(op.join(user_fol, 'connectivity', '*_labels_avg.npz'))
    atlas = bpy.context.scene.atlas
    if len(conn_labels_avg_files) > 0:
        files_names = [mu.namebase(fname).replace('_', ' ').replace('{} '.format(atlas), '') for fname in conn_labels_avg_files]
        items = [(c, c, '', ind) for ind, c in enumerate(files_names)]
        bpy.types.Scene.conn_labels_avg_files = bpy.props.EnumProperty(
            items=items, description="Connectivity labels avg")
        bpy.context.scene.conn_labels_avg_files = files_names[0]
        ColoringMakerPanel.conn_labels_avg_files_exit = True


def register():
    try:
        bpy.utils.register_class(ColorElectrodes)
        bpy.utils.register_class(ColorElectrodesDists)
        bpy.utils.register_class(ColorElectrodesStim)
        bpy.utils.register_class(ColorElectrodesLabels)
        bpy.utils.register_class(ColorContours)
        bpy.utils.register_class(NextLabelConture)
        bpy.utils.register_class(PrevLabelConture)
        bpy.utils.register_class(ColorManually)
        bpy.utils.register_class(ColorVol)
        bpy.utils.register_class(ColorGroupsManually)
        bpy.utils.register_class(ColorMeg)
        bpy.utils.register_class(ColorMegMax)
        bpy.utils.register_class(ColorMegLabels)
        bpy.utils.register_class(ColorfMRI)
        bpy.utils.register_class(ColorfMRILabels)
        bpy.utils.register_class(ColorfMRIDynamics)
        bpy.utils.register_class(ColorClustersFmri)
        bpy.utils.register_class(ColorMEGSensors)
        bpy.utils.register_class(ColorEEGSensors)
        bpy.utils.register_class(ColorEEGHelmet)
        bpy.utils.register_class(ColorConnections)
        bpy.utils.register_class(ColorConnectionsLabelsAvg)
        bpy.utils.register_class(ClearColors)
        bpy.utils.register_class(ColoringMakerPanel)
        bpy.utils.register_class(ChooseLabelFile)
        bpy.utils.register_class(ColorStaticConnectionsDegree)
        # print('Freeview Panel was registered!')
    except:
        print("Can't register Freeview Panel!")


def unregister():
    try:
        bpy.utils.unregister_class(ColorElectrodes)
        bpy.utils.unregister_class(ColorElectrodesDists)
        bpy.utils.unregister_class(ColorElectrodesStim)
        bpy.utils.unregister_class(ColorElectrodesLabels)
        bpy.utils.unregister_class(ColorManually)
        bpy.utils.unregister_class(ColorContours)
        bpy.utils.unregister_class(NextLabelConture)
        bpy.utils.unregister_class(PrevLabelConture)
        bpy.utils.unregister_class(ColorVol)
        bpy.utils.unregister_class(ColorGroupsManually)
        bpy.utils.unregister_class(ColorMeg)
        bpy.utils.unregister_class(ColorMegMax)
        bpy.utils.unregister_class(ColorMegLabels)
        bpy.utils.unregister_class(ColorfMRI)
        bpy.utils.unregister_class(ColorfMRILabels)
        bpy.utils.unregister_class(ColorfMRIDynamics)
        bpy.utils.unregister_class(ColorClustersFmri)
        bpy.utils.unregister_class(ColorMEGSensors)
        bpy.utils.unregister_class(ColorEEGSensors)
        bpy.utils.unregister_class(ColorEEGHelmet)
        bpy.utils.unregister_class(ColorConnections)
        bpy.utils.unregister_class(ColorConnectionsLabelsAvg)
        bpy.utils.unregister_class(ClearColors)
        bpy.utils.unregister_class(ColoringMakerPanel)
        bpy.utils.unregister_class(ChooseLabelFile)
        bpy.utils.unregister_class(ColorStaticConnectionsDegree)
    except:
        pass
        # print("Can't unregister Freeview Panel!")


if __name__ == '__main__':
    import mne
    stc = mne.read_source_estimate('/homes/5/npeled/space1/mmvt/fsaverage5/meg/fsaverage5_msit_nTSSS_interference_diff_1-15-dSPM-lh.stc')
    plot_stc(stc, 100, threshold=1, save_image=False, view_selected=False, subject='fsaverage5', n_jobs=4)