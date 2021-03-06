# Blender and addon libs
try:
    import bpy
    import mathutils
    import colors_utils as cu
except:
    pass
    # print("Can't import bpy, mathutils and color_utils")

# Not vanilla python libs
try:
    import numpy as np
except:
    pass

try:
    import mne
    MNE_EXIST = True
except:
    MNE_EXIST = False

import traceback
import math
import sys
import os
import os.path as op
import re
import uuid
from collections import OrderedDict, Iterable
import time
import subprocess
from subprocess import Popen, PIPE, STDOUT
from multiprocessing.connection import Client
import threading
from queue import Queue
import cProfile
from itertools import chain
from sys import platform as _platform
from datetime import datetime
from queue import Empty
import glob

_addon = None


class empty_bpy(object):
    class types(object):
        class Scene(object): pass
        class Panel(object): pass
        Operator = object
    class props(object):
        class BoolProperty(object):
            def __init__(self, **kargs): pass
        class EnumProperty(object):
            def __init__(self, **kargs): pass
        class FloatProperty(object):
            def __init__(self, **kargs): pass


class empty_bpy_extras(object):
    class io_utils(object):
        class ExportHelper(object): pass

try:
    import connections_panel as con_pan
except:
    try:
        sys.path.append(op.split(__file__)[0])
        import connections_panel as con_pan
    except:
        print('no bpy')

IS_LINUX = _platform == "linux" or _platform == "linux2"
IS_MAC = _platform == "darwin"
IS_WINDOWS = _platform == "win32"

print('platform: {}'.format(_platform))

HEMIS = ['rh', 'lh']
INF_HEMIS = ['inflated_{}'.format(hemi) for hemi in HEMIS]
(OBJ_TYPE_CORTEX_RH, OBJ_TYPE_CORTEX_LH, OBJ_TYPE_CORTEX_INFLATED_RH, OBJ_TYPE_CORTEX_INFLATED_LH, OBJ_TYPE_SUBCORTEX,
    OBJ_TYPE_ELECTRODE, OBJ_TYPE_EEG, OBJ_TYPE_CEREBELLUM, OBJ_TYPE_CON, OBJ_TYPE_CON_VERTICE, OBJ_TYPE_LABEL) = \
    range(11)
OBJ_TYPES_ROIS = [OBJ_TYPE_CORTEX_RH, OBJ_TYPE_CORTEX_LH, OBJ_TYPE_CORTEX_INFLATED_RH, OBJ_TYPE_CORTEX_INFLATED_LH]

show_hide_icon = dict(show='RESTRICT_VIEW_OFF', hide='RESTRICT_VIEW_ON')

try:
    import cPickle as pickle
except:
    import pickle

try:
    from scripts import scripts_utils as su
except:
    from src.mmvt_addon.scripts import scripts_utils as su

get_link_dir = su.get_link_dir
get_links_dir = su.get_links_dir
get_resources_dir = su.get_resources_dir
get_mmvt_dir = su.get_mmvt_dir
get_subjects_dir = su.get_subjects_dir

floats_const_pattern = r"""
     [-+]?
     (?: \d* \. \d+ )
     """
floats_pattern_rx = re.compile(floats_const_pattern, re.VERBOSE)

numeric_const_pattern = r"""
     [-+]? # optional sign
     (?:
         (?: \d* \. \d+ ) # .1 .12 .123 etc 9.1 etc 98.1 etc
         |
         (?: \d+ \.? ) # 1. 12. 123. etc 1 12 123 etc
     )
     # followed by optional exponent part if desired
     # (?: [Ee] [+-]? \d+ ) ?
     """
numeric_pattern_rx = re.compile(numeric_const_pattern, re.VERBOSE)


def read_floats_rx(str):
    return floats_pattern_rx.findall(str)


def read_numbers_rx(str):
    return numeric_pattern_rx.findall(str)


def is_mac():
    return IS_MAC


def is_windows():
    return IS_WINDOWS


def is_linux():
    return IS_LINUX


def namebase(fname):
    name_with_ext = fname.split(op.sep)[-1]
    if not name_with_ext.endswith('nii.gz'):
        return '.'.join(name_with_ext.split('.')[:-1])
    else:
        return name_with_ext[:-len('.nii.gz')]


# def namebase(file_name):
#     if file_name[-1] == op.sep:
#         file_name = file_name[:-1]
#     return op.splitext(op.basename(file_name))[0]


def namesbase_with_ext(fname):
    return fname.split(op.sep)[-1]


def get_fname_folder(fname):
    return op.sep.join(fname.split(op.sep)[:-1])


def file_type(fname):
    if fname.endswith('nii.gz'):
        return 'nii.gz'
    else:
        return fname.split('.')[-1]

# def file_type(fname):
#     return op.splitext(op.basename(fname))[1][1:]


def file_fol():
    return os.path.dirname(bpy.data.filepath)


def save(obj, fname):
    with open(fname, 'wb') as fp:
        pickle.dump(obj, fp, protocol=4)


def load(fname):
    with open(fname, 'rb') as fp:
        obj = pickle.load(fp)
    if obj is None:
        print('the data in {} is None!'.format(fname))
    return obj


class Bag( dict ):
    """ a dict with d.key short for d["key"]
        d = Bag( k=v ... / **dict / dict.items() / [(k,v) ...] )  just like dict
    """
        # aka Dotdict

    def __init__(self, *args, **kwargs):
        dict.__init__( self, *args, **kwargs )
        self.__dict__ = self

    def __getnewargs__(self):  # for cPickle.dump( d, file, protocol=-1)
        return tuple(self)


def add_keyframe(parent_obj, conn_name, value, T):
    try:
        insert_keyframe_to_custom_prop(parent_obj, conn_name, 0, 0)
        insert_keyframe_to_custom_prop(parent_obj, conn_name, value, 1)
        insert_keyframe_to_custom_prop(parent_obj, conn_name, value, T)
        insert_keyframe_to_custom_prop(parent_obj, conn_name, 0, T + 1)
        # print('insert keyframe with value of {}'.format(value))
    except:
        print("Can't add a keyframe! {}, {}, {}".format(parent_obj, conn_name, value))
        print(traceback.format_exc())


def insert_keyframe_to_custom_prop(obj, prop_name, value, keyframe):
    bpy.context.scene.objects.active = obj
    obj.select = True
    obj[prop_name] = value
    obj.keyframe_insert(data_path='[' + '"' + prop_name + '"' + ']', frame=keyframe)


def create_and_set_material(obj):
    # curMat = bpy.data.materials['OrigPatchesMat'].copy()
    if obj.active_material is None or obj.active_material.name != obj.name + '_Mat':
        if obj.name + '_Mat' in bpy.data.materials:
            cur_mat = bpy.data.materials[obj.name + '_Mat']
        else:
            cur_mat = bpy.data.materials['Deep_electrode_mat'].copy()
            cur_mat.name = obj.name + '_Mat'
        # Wasn't it originally (0, 0, 1, 1)?
        cur_mat.node_tree.nodes["RGB"].outputs[0].default_value = (1, 1, 1, 1) # (0, 0, 1, 1) # (0, 1, 0, 1)
        obj.active_material = cur_mat


def mark_objects(objs_names):
    for obj_name in objs_names:
        if bpy.data.objects.get(obj_name):
            bpy.data.objects[obj_name].active_material = bpy.data.materials['selected_label_Mat']


def cylinder_between(p1, p2, r, layers_array):
    # From http://blender.stackexchange.com/questions/5898/how-can-i-create-a-cylinder-linking-two-points-with-python
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    dist = math.sqrt(dx**2 + dy**2 + dz**2)

    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=dist, location=(dx/2 + x1, dy/2 + y1, dz/2 + z1))#, layers=layers_array)

    phi = math.atan2(dy, dx)
    theta = math.acos(dz/dist)
    bpy.context.object.rotation_euler[1] = theta
    bpy.context.object.rotation_euler[2] = phi
    bpy.ops.object.move_to_layer(layers=layers_array)


def create_empty_if_doesnt_exists(name, brain_layer, layers_array=None, root_fol='Brain'):
    if not bpy.data.objects.get(root_fol):
        print('root fol, {}, does not exist'.format(root_fol))
        return
    if layers_array is None:
        # layers_array = bpy.context.scene.layers
        layers_array = [False] * 20
        layers_array[brain_layer] = True
    if bpy.data.objects.get(name) is None:
        # layers_array[brain_layer] = True
        bpy.ops.object.empty_add(type='PLAIN_AXES', radius=1, view_align=False, location=(0, 0, 0), layers=layers_array)
        bpy.ops.object.move_to_layer(layers=layers_array)
        bpy.data.objects['Empty'].name = name
        if name != root_fol:
            bpy.data.objects[name].parent = bpy.data.objects[root_fol]
    return bpy.data.objects[name]


def select_hierarchy(obj, val=True, select_parent=True):
    if bpy.data.objects.get(obj) is not None:
        bpy.data.objects[obj].select = select_parent
        for child in bpy.data.objects[obj].children:
            if val:
                child.hide_select = False
            child.select = val


def create_material(name, diffuseColors, transparency, copy_material=True):
    curMat = bpy.context.active_object.active_material
    if copy_material or 'MyColor' not in curMat.node_tree.nodes:
        #curMat = bpy.data.materials['OrigPatchesMat'].copy()
        curMat = bpy.data.materials['OrigPatchMatTwoCols'].copy()
        curMat.name = name
        bpy.context.active_object.active_material = curMat
    curMat.node_tree.nodes['MyColor'].inputs[0].default_value = diffuseColors
    curMat.node_tree.nodes['MyColor1'].inputs[0].default_value = diffuseColors
    curMat.node_tree.nodes['MyTransparency'].inputs['Fac'].default_value = transparency
    bpy.context.active_object.active_material.diffuse_color = diffuseColors[:3]


def delete_hierarchy(parent_obj_name, exceptions=(), delete_only_animation=False):
    bpy.ops.object.select_all(action='DESELECT')
    obj = bpy.data.objects.get(parent_obj_name)
    if obj is None:
        return
    obj.animation_data_clear()
    # Go over all the objects in the hierarchy like @zeffi suggested:
    names = set()
    def get_child_names(obj):
        for child in obj.children:
            names.add(child.name)
            if child.children:
                get_child_names(child)

    get_child_names(obj)
    names = names - set(exceptions)
    # Remove the animation from the all the child objects
    for child_name in names:
        bpy.data.objects[child_name].animation_data_clear()

    bpy.context.scene.objects.active = obj
    if not delete_only_animation:
        objects = bpy.data.objects
        [setattr(objects[n], 'select', True) for n in names]
        result = bpy.ops.object.delete()
        if result == {'FINISHED'}:
            print ("Successfully deleted object")
        else:
            print ("Could not delete object")


def get_atlas(default='laus250'):
    # name_split = namebase(bpy.data.filepath).split('_')
    # if len(name_split) > 1:
    #     return name_split[1]
    # else:
    #     return default
    blend_fname = namebase(bpy.data.filepath)
    if blend_fname.find('_') == -1:
        print("Can't find the atlas in the blender file! The Blender's file name needs to end with " + \
                        "'_atlas-name.blend' (sub1_dkt.blend for example)")
        return ''
    atlas = blend_fname.split('_')[-1]
    return get_real_atlas_name(atlas)


def get_real_atlas_name(atlas, csv_fol=''):
    if csv_fol == '':
        csv_fol = get_mmvt_root()
    csv_fname = op.join(csv_fol, 'atlas.csv')
    real_atlas_name = ''
    if op.isfile(csv_fname):
        for line in csv_file_reader(csv_fname, ',', 1):
            if len(line) < 2:
                continue
            if atlas in [line[0], line[1]]:
                real_atlas_name = line[1]
                break
        if real_atlas_name == '':
            print("Can't find the atlas {} in {}! Please add it to the csv file.".format(atlas, csv_fname))
            return atlas
        return real_atlas_name
    else:
        print('No atlas file was found! Please create a atlas file (csv) in {}, where '.format(csv_fname) +
                        'the columns are name in blend file, annot name, description')
        return ''


def get_mmvt_fol():
    return bpy.path.abspath('//')


def get_user_fol():
    root_fol = bpy.path.abspath('//')
    user = get_user()
    return op.join(root_fol, user)


def view_all_in_graph_editor(context=None):
    try:
        if context is None:
            context = bpy.context
        graph_area = [context.screen.areas[k] for k in range(len(context.screen.areas)) if
                      context.screen.areas[k].type == 'GRAPH_EDITOR'][0]
        graph_window_region = [graph_area.regions[k] for k in range(len(graph_area.regions)) if
                               graph_area.regions[k].type == 'WINDOW'][0]
        # ui = [graph_area.regions[k] for k in range(len(graph_area.regions)) if graph_area.regions[k].type == 'UI'][0]

        c = context.copy()  # copy the context
        c['area'] = graph_area
        c['region'] = graph_window_region
        bpy.ops.graph.view_all(c)
    except:
        pass


def show_hide_hierarchy(val, obj_name, also_parent=False, select=True):
    if bpy.data.objects.get(obj_name) is not None:
        if also_parent:
            bpy.data.objects[obj_name].hide_render = not val
        for child in bpy.data.objects[obj_name].children:
            child.hide = not val
            child.hide_render = not val
            if select:
                child.select = val


def rand_letters(num):
    return str(uuid.uuid4())[:num]


def evaluate_fcurves(parent_obj, time_range, specific_condition=None):
    data = OrderedDict()
    colors = OrderedDict()
    for fcurve in parent_obj.animation_data.action.fcurves:
        if fcurve.hide:
            continue
        name = fcurve.data_path.split('"')[1]
        if not specific_condition is None:
            cond = name[len(parent_obj.name) + 1:]
            if cond != specific_condition:
                continue
        print('{} extrapolation'.format(name))
        # todo: we should return the interpolation to its previous value
        for kf in fcurve.keyframe_points:
            kf.interpolation = 'BEZIER'
        data[name] = []
        for t in time_range:
            d = fcurve.evaluate(t)
            data[name].append(d)
        colors[name] = tuple(fcurve.color)
    return data, colors


def get_fcurve_current_frame_val(parent_obj_name, obj_name, cur_frame):
    for fcurve in bpy.data.objects[parent_obj_name].animation_data.action.fcurves:
        name = get_fcurve_name(fcurve)
        if name == obj_name:
            return fcurve.evaluate(cur_frame)


def get_fcurve_name(fcurve):
    return fcurve.data_path.split('"')[1]


def show_only_selected_fcurves(context):
    space = context.space_data
    dopesheet = space.dopesheet
    dopesheet.show_only_selected = True


# def get_fcurve_values(parent_name, fcurve_name):
#     xs, ys = [], []
#     parent_obj = bpy.data.objects[parent_name]
#     for fcurve in parent_obj.animation_data.action.fcurves:
#         if get_fcurve_name(fcurve) == fcurve_name:
#             for kp in fcurve.keyframe_points:
#                 xs.append(kp.co[0])
#                 ys.append(kp.co[1])
#     return xs, ys


def time_to_go(now, run, runs_num, runs_num_to_print=10, thread=-1):
    if run % runs_num_to_print == 0 and run != 0:
        time_took = time.time() - now
        more_time = time_took / run * (runs_num - run)
        if thread > 0:
            print('{}: {}/{}, {:.2f}s, {:.2f}s to go!'.format(thread, run, runs_num, time_took, more_time))
        else:
            print('{}/{}, {:.2f}s, {:.2f}s to go!'.format(run, runs_num, time_took, more_time))


def show_hide_obj_and_fcurves(objs, val, exclude=[]):
    if not isinstance(objs, Iterable):
        objs = [objs]
    for obj in objs:
        if obj.name in exclude:
            continue
        obj.select = val
        if obj.animation_data:
            for fcurve in obj.animation_data.action.fcurves:
                fcurve_name = get_fcurve_name(fcurve)
                if fcurve_name in exclude:
                    fcurve.hide = True
                    fcurve.select = False
                else:
                    fcurve.hide = not val
                    fcurve.select = val
        else:
            pass
            # print('No animation in {}'.format(obj.name))


def message(self, message):
    # todo: Find how to send messaages without the self
    if self:
        self.report({'ERROR'}, message)
    else:
        print(message)


def show_only_group_objects(objects, group_name='new_filter'):
    ge = get_the_graph_editor()
    dopesheet = ge.dopesheet
    # space = context.space_data
    # dopesheet = space.dopesheet
    selected_group = bpy.data.groups.get(group_name, bpy.data.groups.new(group_name))
    for obj in objects:
        if isinstance(obj, str):
            obj = bpy.data.objects[obj]
        selected_group.objects.link(obj)
    dopesheet.filter_group = selected_group
    dopesheet.show_only_group_objects = True


def create_sphere(loc, rad, my_layers, name):
    bpy.ops.mesh.primitive_uv_sphere_add(
        ring_count=30, size=rad, view_align=False, enter_editmode=False, location=loc, layers=my_layers)
    bpy.ops.object.shade_smooth()
    bpy.context.active_object.name = name


def create_ico_sphere(location, layers, name, size=.3, subdivisions=2, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_ico_sphere_add(
        location=location, layers=layers, size=size, subdivisions=subdivisions,rotation=rotation)
    bpy.ops.object.shade_smooth()
    bpy.context.active_object.name = name
    return bpy.context.active_object


def create_spline(points, layers_array, bevel_depth=0.045, resolution_u=5):
    # points = [ [1,1,1], [-1,1,1], [-1,-1,1], [1,-1,-1] ]
    curvedata = bpy.data.curves.new(name="Curve", type='CURVE')
    curvedata.dimensions = '3D'
    curvedata.fill_mode = 'FULL'
    curvedata.bevel_depth = bevel_depth
    ob = bpy.data.objects.new("CurveObj", curvedata)
    bpy.context.scene.objects.link(ob)

    spline = curvedata.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for num in range(len(spline.bezier_points)):
        spline.bezier_points[num].co = points[num]
        spline.bezier_points[num].handle_right_type = 'AUTO'
        spline.bezier_points[num].handle_left_type = 'AUTO'
    spline.resolution_u = resolution_u
    #spline.order_u = 6
    #spline.use_bezier_u = True
    #spline.radius_interpolation = 'BSPLINE'
    #print(spline.type)
    #spline.use_smooth = True
    bpy.ops.object.move_to_layer(layers=layers_array)
    return ob


def get_subfolders(fol):
    return [os.path.join(fol,subfol) for subfol in os.listdir(fol) if os.path.isdir(os.path.join(fol,subfol))]


def hemi_files_exists(fname):
    return os.path.isfile(fname.format(hemi='rh')) and \
           os.path.isfile(fname.format(hemi='lh'))


def atoi(text):
    return int(text) if text.isdigit() else text


def natural_keys(text):
    # http://stackoverflow.com/questions/5967500/how-to-correctly-sort-a-string-with-a-number-inside
    if isinstance(text, tuple):
        text = text[0]
    return [atoi(c) for c in re.split('(\d+)', text)]


def elec_group_number(elec_name, bipolar=False):
    if isinstance(elec_name, bytes):
        elec_name = elec_name.decode('utf-8')
    if bipolar and '-' in elec_name:
        elec_name2, elec_name1 = elec_name.split('-')
        group1, num1 = elec_group_number(elec_name1, False)
        group2, num2 = elec_group_number(elec_name2, False)
        group = group1 if group1 != '' else group2
        return group, num1, num2
    else:
        elec_name = elec_name.strip()
        num = re.sub('\D', ',', elec_name).split(',')[-1]
        group = elec_name[:elec_name.rfind(num)]
        return group, int(num) if num != '' else ''


def elec_group(elec_name, bipolar=False):
    #todo: should check the electrode type, if it's grid, it should be bipolar
    if '-' in elec_name:
        group, _, _ = elec_group_number(elec_name, True)
    else:
        group, _ = elec_group_number(elec_name, False)
    return group


def csv_file_reader(csv_fname, delimiter=',', skip_header=0):
    import csv
    with open(csv_fname, 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=delimiter)
        for line_num, line in enumerate(reader):
            if line_num < skip_header:
                continue
            yield [val.strip() for val in line]


def check_obj_type(obj_name):
    obj = bpy.data.objects.get(obj_name, None)
    if obj is None:
        obj_type = None
    elif obj.parent is None:
        obj_type = None
    elif obj.parent.name == 'Cortex-lh':
        obj_type = OBJ_TYPE_CORTEX_LH
    elif obj.parent.name == 'Cortex-rh':
        obj_type = OBJ_TYPE_CORTEX_RH
    elif obj.parent.name == 'Cortex-inflated-lh':
        obj_type = OBJ_TYPE_CORTEX_INFLATED_LH
    elif obj.parent.name == 'Cortex-inflated-rh':
        obj_type = OBJ_TYPE_CORTEX_INFLATED_RH
    elif obj.parent.name == 'Subcortical_structures':
        obj_type = OBJ_TYPE_SUBCORTEX
    elif obj.parent.name == 'Deep_electrodes':
        obj_type = OBJ_TYPE_ELECTRODE
    elif obj.parent.name == 'EEG_sensors':
        obj_type = OBJ_TYPE_EEG
    elif obj.parent.name in ['Cerebellum', 'Cerebellum_fmri_activity_map', 'Cerebellum_meg_activity_map']:
        obj_type = OBJ_TYPE_CEREBELLUM
    elif obj.parent.name == con_pan.get_connections_parent_name():
        obj_type = OBJ_TYPE_CON
    elif obj.parent.name == 'connections_vertices':
        obj_type = OBJ_TYPE_CON_VERTICE
    else:
        obj_type = None
        # print("Can't find the object type ({})!".format(obj_name))
    return obj_type


def get_obj_hemi(obj_name):
    obj_type = check_obj_type(obj_name)
    if obj_type == OBJ_TYPE_CORTEX_LH:
        hemi = 'lh'
    elif obj_type == OBJ_TYPE_CORTEX_RH:
        hemi = 'rh'
    else:
        hemi = None
    return hemi


def run_command_in_new_thread(cmd, queues=True, shell=True, read_stdin=True, read_stdout=True, read_stderr=False,
                              stdin_func=lambda: True, stdout_func=lambda: True, stderr_func=lambda: True, cwd=None):
    if queues:
        q_in, q_out = Queue(), Queue()
        thread = threading.Thread(target=run_command_and_read_queue, args=(
            cmd, q_in, q_out, shell, read_stdin, read_stdout, read_stderr,
            stdin_func, stdout_func, stderr_func, cwd))
    else:
        thread = threading.Thread(target=run_command, args=(cmd, shell, cwd))
        q_in, q_out = None, None
    print('start!')
    thread.start()
    return q_in, q_out


def run_command_and_read_queue(cmd, q_in, q_out, shell=True, read_stdin=True, read_stdout=True, read_stderr=False,
                               stdin_func=lambda:True, stdout_func=lambda:True, stderr_func=lambda:True, cwd=None):

    def write_to_stdin(proc, q_in, while_func):
        while while_func():
            # Get some data
            data = q_in.get()
            try:
                print('Writing data into stdin: {}'.format(data))
                output = proc.stdin.write(data.encode())  # decode('utf-8'))
                proc.stdin.flush()
                print('stdin output: {}'.format(output))
            except:
                print("Something is wrong with the in pipe, can't write to stdin!!!")
                break
                # print(traceback.format_exc())
        print('End of write_to_stdin')

    def read_from_stdout(proc, q_out, while_func):
        while while_func():
            try:
                line = proc.stdout.readline()
                if line != b'':
                    q_out.put(line)
                    # print('stdout: {}'.format(line))
            except:
                print('Error in reading stdout!!!')
                break
                # print(traceback.format_exc())
        print('End of read_from_stdout')

    def read_from_stderr(proc, while_func):
        while while_func():
            try:
                line = proc.stderr.readline()
                line = line.decode(sys.getfilesystemencoding(), 'ignore')
                if line != '':
                    print('stderr: {}'.format(line))
            except:
                print('Error in reading stderr!!!')
                break
                # print(traceback.format_exc())
        print('End of read_from_stderr')

    stdout = PIPE if read_stdout else None
    stdin = PIPE if read_stdin else None
    stderr = PIPE if read_stderr else None
    p = Popen(cmd, shell=shell, stdout=stdout, stdin=stdin, stderr=stderr, bufsize=1, close_fds=True, cwd=cwd) #, universal_newlines=True)
    if read_stdin:
        thread_write_to_stdin = threading.Thread(target=write_to_stdin, args=(p, q_in, stdin_func))
        thread_write_to_stdin.start()
    if read_stdout:
        thread_read_from_stdout = threading.Thread(target=read_from_stdout, args=(p, q_out, stdout_func))
        thread_read_from_stdout.start()
    if read_stderr:
        thread_read_from_stderr = threading.Thread(target=read_from_stderr, args=(p, stderr_func))
        thread_read_from_stderr.start()


def run_thread(target_func, while_func=lambda:True, **kwargs):
    q = Queue()
    t = threading.Thread(target=target_func, args=(q, while_func), kwargs=kwargs)
    t.start()
    return q


def run_thread_2q(target_func, while_func=lambda:True, **kwargs):
    q1, q2 = Queue(), Queue()
    t = threading.Thread(target=target_func, args=(q1, q2, while_func), kwargs=kwargs)
    t.start()
    return q1, q2


def run_command(cmd, shell=True, pipe=False, cwd=None):
    # global p
    from subprocess import Popen, PIPE, STDOUT
    print('run: {}'.format(cmd))
    if (IS_WINDOWS):
        os.system(cmd)
        return None
    else:
        if pipe:
            p = Popen(cmd, shell=True, stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=cwd)
        else:
            p = subprocess.call(cmd, shell=shell, cwd=cwd)
        # p = Popen(cmd, shell=True, stdout=PIPE, stdin=PIPE, stderr=PIPE)
        # p.stdin.write(b'-zoom 2\n')
        return p


# class Unbuffered(object):
#    def __init__(self, stream):
#        self.stream = stream
#    def write(self, data):
#        self.stream.write(dataf)
#        self.stream.flush()
#    def __getattr__(self, attr):
#        return getattr(self.stream, attr)
#
# import sys
# sys.stdout = Unbuffered(sys.stdout)


def make_dir(fol):
    if not os.path.isdir(fol):
        os.makedirs(fol)
    return fol


def profileit(sort_field='cumtime', root_folder=''):
    """
    Parameters
    ----------
    prof_fname
        profile output file name
    sort_field
        "calls"     : (((1,-1),              ), "call count"),
        "ncalls"    : (((1,-1),              ), "call count"),
        "cumtime"   : (((3,-1),              ), "cumulative time"),
        "cumulative": (((3,-1),              ), "cumulative time"),
        "file"      : (((4, 1),              ), "file name"),
        "filename"  : (((4, 1),              ), "file name"),
        "line"      : (((5, 1),              ), "line number"),
        "module"    : (((4, 1),              ), "file name"),
        "name"      : (((6, 1),              ), "function name"),
        "nfl"       : (((6, 1),(4, 1),(5, 1),), "name/file/line"),
        "pcalls"    : (((0,-1),              ), "primitive call count"),
        "stdname"   : (((7, 1),              ), "standard name"),
        "time"      : (((2,-1),              ), "internal time"),
        "tottime"   : (((2,-1),              ), "internal time"),
    Returns
    -------
    None

    """

    def actual_profileit(func):
        def wrapper(*args, **kwargs):
            prof = cProfile.Profile()
            retval = prof.runcall(func, *args, **kwargs)
            prof_root_folder = get_user_fol() if root_folder == '' else root_folder
            make_dir(prof_root_folder)
            prof_dir = op.join(prof_root_folder, 'profileit')
            make_dir(prof_dir)
            prof_fname = op.join(prof_dir, '{}_{}'.format(func.__name__, rand_letters(5)))
            stat_fname = '{}.stat'.format(prof_fname)
            prof.dump_stats(prof_fname)
            print_profiler(prof_fname, stat_fname, sort_field)
            print('dump stat in {}'.format(stat_fname))
            return retval
        return wrapper
    return actual_profileit


def print_profiler(profile_input_fname, profile_output_fname, sort_field='cumtime'):
    import pstats
    with open(profile_output_fname, 'w') as f:
        stats = pstats.Stats(profile_input_fname, stream=f)
        stats.sort_stats(sort_field)
        stats.print_stats()


def timeit(func):
    def wrapper(*args, **kwargs):
        now = time.time()
        retval = func(*args, **kwargs)
        print('{} took {:.5f}s'.format(func.__name__, time.time() - now))
        return retval

    return wrapper


def dump_args(func):
    # Decorator to print function call details - parameters names and effective values
    # http://stackoverflow.com/a/25206079/1060738
    def wrapper(*func_args, **func_kwargs):
        arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]
        args = func_args[:len(arg_names)]
        defaults = func.__defaults__ or ()
        args = args + defaults[len(defaults) - (func.__code__.co_argcount - len(args)):]
        params = list(zip(arg_names, args))
        args = func_args[len(arg_names):]
        if args: params.append(('args', args))
        if func_kwargs: params.append(('kwargs', func_kwargs))
        try:
            return func(*func_args, **func_kwargs)
        except:
            print('Error in {}!'.format(func.__name__))
            print(func.__name__ + ' (' + ', '.join('%s = %r' % p for p in params) + ' )')
            print(traceback.format_exc())
            # try:
            #     print('Current context:')
            #     get_current_context()
            # except:
            #     print('Error finding the context!')
            #     print(traceback.format_exc())
    return wrapper


# def tryit(throw_exception=True):
def tryit(except_retval=False, throw_exception=False):
    def real_tryit(func):
        def wrapper(*args, **kwargs):
            try:
                retval = func(*args, **kwargs)
            except:
                print('Error in {}!'.format(func.__name__))
                if (throw_exception):
                    raise Exception(traceback.format_exc())
                print(traceback.format_exc())
                retval = except_retval
            return retval
        return wrapper
    return real_tryit


def get_all_children(parents):
    children = [bpy.data.objects[parent].children for parent in parents if bpy.data.objects.get(parent)]
    return list(chain.from_iterable([obj for obj in children]))


def get_non_functional_objects():
    return get_all_children((['Cortex-lh', 'Cortex-rh', 'Subcortical_structures', 'Deep_electrodes', 'External']))


def get_selected_objects():
    return [obj for obj in get_non_functional_objects() if obj.select]


def get_corticals_labels():
    return bpy.data.objects['Cortex-lh'].children + bpy.data.objects['Cortex-rh'].children


def add_box_line(col, text1, text2='', percentage=0.3, align=True):
    row = col.split(percentage=percentage, align=align)
    row.label(text=text1)
    if text2 != '':
        row.label(text=text2)


def get_user():
    return namebase(bpy.data.filepath).split('_')[0]


def current_path():
    return os.path.dirname(os.path.realpath(__file__))


def get_parent_fol(fol=None):
    if fol is None:
        fol = os.path.dirname(os.path.realpath(__file__))
    return os.path.split(fol)[0]


def get_mmvt_code_root():
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.dirname(os.path.split(curr_dir)[0])


def get_mmvt_root():
    return get_parent_fol(get_user_fol())


def change_fol_to_mmvt_root():
    os.chdir(get_mmvt_code_root())


class connection_to_listener(object):
    # http://stackoverflow.com/a/6921402/1060738

    conn = None
    handle_is_open = False

    @staticmethod
    def check_if_open():
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = s.connect_ex(('localhost', 6000))

        if result == 0:
            print('socket is open')
        s.close()

    def init(self):
        try:
            # connection_to_listener.check_if_open()
            # connection_to_listener.run_addon_listener()
            address = ('localhost', 6000)
            self.conn = Client(address, authkey=b'mmvt')
            self.handle_is_open = True
            return True
        except:
            print('Error in connection_to_listener.init()!')
            print(traceback.format_exc())
            return False

    @staticmethod
    def run_addon_listener():
        cmd = 'python {}'.format(op.join(current_path(), 'addon_listener.py'))
        print('Running {}'.format(cmd))
        run_command_in_new_thread(cmd, shell=True)
        time.sleep(1)

    def send_command(self, cmd):
        if self.handle_is_open:
            self.conn.send(cmd)
            return True
        else:
            # print('Handle is close')
            return False

    def close(self):
        self.send_command('close\n')
        self.conn.close()
        self.handle_is_open = False

conn_to_listener = connection_to_listener()


def min_cdist_from_obj(obj, Y):
    vertices = obj.data.vertices
    kd = mathutils.kdtree.KDTree(len(vertices))
    for ind, x in enumerate(vertices):
        kd.insert(x.co, ind)
    kd.balance()
    # Find the closest point to the 3d cursor
    res = []
    for y in Y:
        res.append(kd.find_n(y, 1)[0])
    # co, index, dist
    return res


def min_cdist(X, Y):
    kd = mathutils.kdtree.KDTree(X.shape[0])
    for ind, x in enumerate(X):
        kd.insert(x, ind)
    kd.balance()
    # Find the closest point to the 3d cursor
    res = []
    for y in Y:
        res.append(kd.find_n(y, 1)[0])
    # co, index, dist
    return res


# def cdist(x, y):
#     return np.sqrt(np.dot(x, x) - 2 * np.dot(x, y) + np.dot(y, y))


# Warning! This method is really slow, ~3s per hemi
def obj_has_activity(obj):
    activity = False
    for mesh_loop_color_layer_data in obj.data.vertex_colors.active.data:
        if tuple(mesh_loop_color_layer_data.color) != (1, 1, 1):
            activity = True
            break
    return activity


def other_hemi(hemi):
    if 'inflated' in hemi:
        return 'inflated_lh' if hemi == 'inflated_rh' else 'inflated_rh'
    else:
        return 'lh' if hemi == 'rh' else 'rh'


# http://blender.stackexchange.com/a/30739/16364
def show_progress(job_name):
    sys.stdout.write('{}: '.format(job_name))
    sys.stdout.flush()
    some_list = [0] * 100
    for idx, item in enumerate(some_list):
        msg = "item %i of %i" % (idx, len(some_list)-1)
        sys.stdout.write(msg + chr(8) * len(msg))
        sys.stdout.flush()
        time.sleep(0.02)

    sys.stdout.write("DONE" + " "*len(msg)+"\n")
    sys.stdout.flush()


def update_progress(job_title, progress):
    length = 20 # modify this to change the length
    block = int(round(length*progress))
    msg = "\r{0}: [{1}] {2}%".format(job_title, "#"*block + "-"*(length-block), round(progress*100, 2))
    if progress >= 1: msg += " DONE\r\n"
    sys.stdout.write(msg)
    sys.stdout.flush()

    def test():
        for i in range(100):
            time.sleep(0.1)
            update_progress("Some job", i / 100.0)
        update_progress("Some job", 1)


def get_spaced_colors(n):
    import colorsys
    # if n <= 7:
    #     colors = ['r', 'g', 'c', 'm', 'y', 'b', 'k'][:n]
    # else:
    HSV_tuples = [(x*1.0/n, 0.5, 0.5) for x in range(n)]
    colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples))
    return colors


def create_empty_in_vertex(vertex_location, obj_name, layer, parent_name=''):
    layers = [False] * 20
    layers[layer] = True
    bpy.ops.object.empty_add(type='PLAIN_AXES', radius=1, view_align=False, location=vertex_location, layers=layers)
    bpy.context.object.name = obj_name
    if parent_name != '' and not bpy.data.objects.get(parent_name, None) is None:
        bpy.context.object.parent = bpy.data.objects[parent_name]


def read_ply_file(ply_file):
    with open(ply_file, 'r') as f:
        lines = f.readlines()
        verts_num = int(lines[2].split(' ')[-1])
        faces_num = int(lines[6].split(' ')[-1])
        verts_lines = lines[9:9 + verts_num]
        faces_lines = lines[9 + verts_num:]
        verts = np.array([list(map(float, l.strip().split(' '))) for l in verts_lines])
        faces = np.array([list(map(int, l.strip().split(' '))) for l in faces_lines])[:,1:]
    return verts, faces


def change_selected_fcurves_colors(selected_objects_types, color_also_objects=True, exclude=()):
    import colorsys
    # print('change_selected_fcurves_colors')
    if not isinstance(selected_objects_types, Iterable):
        selected_objects_types = [selected_objects_types]
    selected_objects = [obj for obj in bpy.context.selected_objects if
                        check_obj_type(obj.name) in selected_objects_types]
    selected_objects = [obj for obj in selected_objects if obj.animation_data is not None and
                        obj.name not in exclude][::-1]
    if len(selected_objects) == 0:
        return
    selected_objects_len = 6 if len(selected_objects) <= 6 else len(selected_objects)
    Hs = np.linspace(0, 360, selected_objects_len + 1)[:-1] / 360
    fcurves_per_obj = count_fcurves(selected_objects[0])
    Ls = [0.3, 0.7] if fcurves_per_obj == 2 else [0.5]

    for obj_ind, obj in enumerate(selected_objects):
        if color_also_objects:
            obj_color = colorsys.hls_to_rgb(Hs[obj_ind], 0.5, 1)
            _addon.object_coloring(obj, obj_color)
        for fcurve_ind, fcurve in enumerate(obj.animation_data.action.fcurves):
            new_color = colorsys.hls_to_rgb(Hs[obj_ind], Ls[fcurve_ind], 1)
            change_fcurve_color(fcurve, new_color, exclude)


def change_fcurves_colors(objs=[], exclude=[], fcurves=[]):
    colors_num = count_fcurves(objs)
    colors = cu.get_distinct_colors(colors_num)
    if len(fcurves) > 0:
        for fcurve in fcurves:
            change_fcurve_color(fcurve, colors, exclude)
    else:
        if not isinstance(objs, Iterable):
            objs = [objs]
        for obj in objs:
            if obj.animation_data is None:
                continue
            if obj.name in exclude:
                continue
            for fcurve in obj.animation_data.action.fcurves:
                change_fcurve_color(fcurve, colors, exclude)


def change_fcurve_color(fcurve, color, exclude=[]):
    fcurve_name = get_fcurve_name(fcurve)
    if fcurve_name in exclude:
        return
    fcurve.color_mode = 'CUSTOM'
    fcurve.color = color if isinstance(color, tuple) and len(color) == 3 else tuple(next(color))
    fcurve.select = True
    fcurve.hide = False


def count_fcurves(objs, recursive=False):
    if not isinstance(objs, Iterable):
        objs = [objs]
    curves_num = 0
    for obj in objs:
        if not obj is None and 'unknown' not in obj.name:
            if not obj is None and not obj.animation_data is None:
                curves_num += len(obj.animation_data.action.fcurves)
        if recursive:
            curves_num += count_fcurves(obj.children)
    return curves_num


def get_fcurves(obj, recursive=False, only_selected=True):
    if isinstance(obj, str):
        obj = bpy.data.objects.get(obj)
        if obj is None:
            return None
    fcurves, fcurves_inds = [], []
    if not obj is None and not obj.animation_data is None:
        if not only_selected or obj.select:
            fcurves.extend(obj.animation_data.action.fcurves)
    if recursive:
        for obj in obj.children:
            if not only_selected or obj.select:
                fcurves.extend(get_fcurves(obj, recursive, only_selected))
    return fcurves


def get_all_selected_fcurves(parent_obj_name):
    children = bpy.data.objects[parent_obj_name].children
    parent_obj = bpy.data.objects[parent_obj_name]
    children_have_fcurves = count_fcurves(children) > 0
    parent_have_fcurves = not parent_obj.animation_data is None
    fcurves = []
    if parent_have_fcurves and (bpy.context.scene.selection_type == 'diff' or not children_have_fcurves):
        fcurves = get_fcurves(parent_obj, recursive=False, only_selected=True)
    elif children_have_fcurves:
        for child in children:
            fcurves.extend(get_fcurves(child, recursive=False, only_selected=True))
    return fcurves


def if_cond_is_diff(parent_obj):
    if isinstance(parent_obj, str):
        parent_obj = bpy.data.objects[parent_obj]
    children = parent_obj.children
    children_have_fcurves = count_fcurves(children) > 0
    parent_have_fcurves = parent_obj.animation_data is not None
    return parent_have_fcurves and (bpy.context.scene.selection_type == 'diff' or not children_have_fcurves)


def get_fcurves_names(obj, recursive=False):
    if isinstance(obj, str):
        obj = bpy.data.objects.get(obj)
    fcurves_names = []
    if not obj is None and not obj.animation_data is None:
        fcurves_names = [get_fcurve_name(fcurve) for fcurve in obj.animation_data.action.fcurves]
    if recursive:
        for obj in obj.children:
            fcurves_names.extend(get_fcurves_names(obj))
    return fcurves_names


def get_the_graph_editor():
    for ii in range(len(bpy.data.screens['Neuro'].areas)):
        if bpy.data.screens['Neuro'].areas[ii].type == 'GRAPH_EDITOR':
            for jj in range(len(bpy.data.screens['Neuro'].areas[ii].spaces)):
                if bpy.data.screens['Neuro'].areas[ii].spaces[jj].type == 'GRAPH_EDITOR':
                    return bpy.data.screens['Neuro'].areas[ii].spaces[jj]
    return None


def set_show_textured_solid(val=True, only_neuro=False):
    for space in get_3d_spaces(only_neuro):
        space.show_textured_solid = val


def show_only_render(val=True, only_neuro=False):
    for space in get_3d_spaces():
        # Don't change it for the colorbar's space
        if space.lock_object and space.lock_object.name == 'full_colorbar':
            continue
        space.show_only_render = val


def hide_relationship_lines(val=False):
    for space in get_3d_spaces():
        # Don't change it for the colorbar's space
        if space.lock_object and space.lock_object.name == 'full_colorbar':
            continue
        space.show_relationship_lines = val


def get_3d_spaces(only_neuro=False):
    for screen in bpy.data.screens:
        areas = bpy.data.screens['Neuro'].areas if only_neuro else screen.areas
        for area in areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        yield space


def filter_graph_editor(filter):
    ge = get_the_graph_editor()
    ge.dopesheet.filter_fcurve_name = filter


def unfilter_graph_editor():
    filter_graph_editor('')



def unique_save_order(arr):
    ret = []
    for val in arr:
        if val not in ret:
            ret.append(val)
    return ret


def remove_items_from_set(x, items):
    for item in items:
        if item in x:
            x.remove(item)


def save_blender_file(blend_fname=''):
    if blend_fname == '':
        blend_fname = bpy.data.filepath
    print('Saving current file to {}'.format(blend_fname))
    bpy.ops.wm.save_as_mainfile(filepath=blend_fname)


def update():
    # return
    # bpy.context.scene.frame_current += 1
    # bpy.data.objects['Brain'].select = True
    # bpy.ops.mmvt.where_i_am()
    # print(bpy.ops.ed.undo())
    # print(bpy.ops.ed.redo())
    # bpy.ops.ed.undo_history()
    bpy.ops.object.editmode_toggle()
    bpy.ops.object.editmode_toggle()


def change_layer(layer):
    bpy.context.scene.layers = [ind == layer for ind in range(len(bpy.context.scene.layers))]


def select_layer(layer, val=True):
    layers = bpy.context.scene.layers
    layers[layer] = val
    bpy.context.scene.layers = layers


def get_time():
    # print(datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'))
    return str(datetime.now())


def get_time_obj():
    return datetime.now()


def get_time_from_event(time_obj):
    return(datetime.now()-time_obj).seconds


# def change_fcurve(obj_name, fcurve_name, data):
#     bpy.data.objects[obj_name].select = True
#     parent_obj = bpy.data.objects[obj_name]
#     for fcurve in parent_obj.animation_data.action.fcurves:
#         if get_fcurve_name(fcurve) == fcurve_name:
#             N = min(len(fcurve.keyframe_points), len(data))
#             for ind in range(N):
#                 fcurve.keyframe_points[ind].co[1] = data[ind]

@timeit
def change_fcurves(obj_name, data, ch_names):
    bpy.data.objects[obj_name].select = True
    parent_obj = bpy.data.objects[obj_name]
    ch_inds = get_fcurves_ordering(obj_name, ch_names)
    for fcurve, ch_ind in zip(parent_obj.animation_data.action.fcurves, ch_inds):
        fcurve_name = get_fcurve_name(fcurve)
        if fcurve_name != ch_names[ch_ind]:
            raise Exception('Wrong ordering!')
        N = min(len(fcurve.keyframe_points), data.shape[1])
        fcurve.keyframe_points[0].co[1] = 0
        for time_ind in range(N):
            fcurve.keyframe_points[time_ind + 1].co[1] = data[ch_ind, time_ind]
        fcurve.keyframe_points[N].co[1] = 0


@timeit
def get_fcurves_data(obj_name='', fcurves=[], with_kids=True, return_names=False):
    if obj_name != '':
        parent_obj = bpy.data.objects[obj_name]
        if parent_obj.animation_data is not None:
            fcurves = parent_obj.animation_data.action.fcurves
        if with_kids:
            for obj in parent_obj.children:
                if obj.animation_data is not None:
                    fcurves.extend(obj.animation_data.action.fcurves)
    if len(fcurves) == 0:
        return []
    T = len(fcurves[0].keyframe_points)
    data = np.zeros((len(fcurves), T))
    for fcurve_ind, fcurve in enumerate(fcurves):
        for time_ind in range(T):
            data[fcurve_ind, time_ind] = fcurve.keyframe_points[time_ind].co[1]
    if return_names:
        names = [get_fcurve_name(f) for f in fcurves]
        return data, names
    else:
        return data


@timeit
def get_fcurves_ordering(obj_name, ch_names):
    parent_obj = bpy.data.objects[obj_name]
    fcurves_names = [get_fcurve_name(fcurve) for fcurve in parent_obj.animation_data.action.fcurves]
    ch_inds = []
    for fcurve_ind, fcurve_name in enumerate(fcurves_names):
        if fcurve_name != ch_names[fcurve_ind]:
            ch_ind = np.where(ch_names == fcurve_name)[0][0]
        else:
            ch_ind = fcurve_ind
        ch_inds.append(ch_ind)
    return ch_inds


def get_data_max_min(data, norm_by_percentile, norm_percs=None, data_per_hemi=False, hemis=HEMIS, symmetric=False):
    if data_per_hemi:
        if norm_by_percentile:
            data_max = max([np.percentile(data[hemi], norm_percs[1]) for hemi in hemis])
            data_min = min([np.percentile(data[hemi], norm_percs[0]) for hemi in hemis])
        else:
            data_max = max([np.max(data[hemi]) for hemi in hemis])
            data_min = min([np.min(data[hemi]) for hemi in hemis])
    else:
        if norm_by_percentile:
            data_max = np.percentile(data, norm_percs[1])
            data_min = np.percentile(data, norm_percs[0])
        else:
            data_max = np.max(data)
            data_min = np.min(data)
    if symmetric:
        data_minmax = get_max_abs(data_max, data_min)
        data_max, data_min = data_minmax, -data_minmax
    return data_max, data_min


def get_max_abs(data_max, data_min):
    return max(map(abs, [data_max, data_min]))


def calc_min_max(x, x_min=None, x_max=None, norm_percs=None):
    if x_min is None:
        x_min = np.nanmin(x) if norm_percs is None else np.percentile(x, norm_percs[0])
    if x_max is None:
        x_max = np.nanmax(x) if norm_percs is None else np.percentile(x, norm_percs[1])
    if x_min == 0 and x_max == 0 and norm_percs is not None:
        x_min, x_max = calc_min_max(x)
    if x_min == 0 and x_max == 0:
        print('calc_min_max: min and max are 0!!!')
    return x_min, x_max


def queue_get(queue):
    try:
        if queue is None:
            return None
        else:
            return queue.get(block=False)
    except Empty:
        return None


class dummy_bpy(object):
    class types(object):
        class Operator(object):
            pass
        class Panel(object):
            pass


def caller_func():
    return sys._getframe(2).f_code.co_name


def log_err(text, logging=None):
    message = '{}: {}'.format(caller_func(), text)
    print(message)
    if not logging is None:
        logging.error(message)


def to_float(x_str, def_val=0.0):
    try:
        return float(x_str)
    except ValueError:
        return def_val


def to_int(x_str, def_val=0):
    try:
        return int(x_str)
    except ValueError:
        return def_val


def counter_to_dict(counter):
    return {k: v for k, v in counter.items()}


def to_str(s):
    if isinstance(s, str):
        return s
    elif (isinstance(s, np.bytes_)):
        return s.decode(sys.getfilesystemencoding(), 'ignore')
    else:
        return str(s)


def read_config_ini(fol='', ini_name='config.ini'):
    import configparser

    class EmptySettings(object):
        def sections(self):
            return {}

    if fol == '':
        fol = get_user_fol()
    if op.isfile(op.join(fol, ini_name)):
        config = configparser.ConfigParser()
        config.read(op.join(fol, ini_name))
    else:
        config = EmptySettings()
    return config


def get_graph_context():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'GRAPH_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = bpy.context.copy()
                        override['area'] = area
                        override["region"] = region
                        return override
    print("Couldn't find the graph editor!")


def set_graph_att(att, val):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'GRAPH_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        bpy.context.scene[att] = val


def get_view3d_context():
    area = bpy.data.screens['Neuro'].areas[1]
    for region in area.regions:
        if region.type == 'WINDOW':
            override = bpy.context.copy()
            override['area'] = area
            override["region"] = region
            return override


def get_image_context():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'IMAGE_EDITOR':
                override = bpy.context.copy()
                override['area'] = area
                override["screen"] = screen
                return override
    print("Can't find image context!")


def view_selected():
    area = bpy.data.screens['Neuro'].areas[1]
    for region in area.regions:
        if region.type == 'WINDOW':
            override = bpy.context.copy()
            override['area'] = area
            override["region"] = region
            select_all_brain(True)
            bpy.ops.view3d.view_selected(override)


def select_all_brain(val):
    bpy.data.objects['lh'].hide_select = not val
    bpy.data.objects['lh'].select = val
    bpy.data.objects['rh'].hide_select = not val
    bpy.data.objects['rh'].select = val
    if not bpy.data.objects['Subcortical_fmri_activity_map'].hide:
        select_hierarchy('Subcortical_fmri_activity_map', val)
        if not val:
            for child in bpy.data.objects['Subcortical_fmri_activity_map'].children:
                child.hide_select = True


def get_view3d_region():
    return bpy.data.screens['Neuro'].areas[1].spaces[0].region_3d


def get_current_context():
    # all the area types except 'EMPTY' from blender.org/api/blender_python_api_current/bpy.types.Area.html#bpy.types.Area.type
    types = {'VIEW_3D', 'TIMELINE', 'GRAPH_EDITOR', 'DOPESHEET_EDITOR', 'NLA_EDITOR', 'IMAGE_EDITOR', 'SEQUENCE_EDITOR',
             'CLIP_EDITOR', 'TEXT_EDITOR', 'NODE_EDITOR', 'LOGIC_EDITOR', 'PROPERTIES', 'OUTLINER', 'USER_PREFERENCES',
             'INFO', 'FILE_BROWSER', 'CONSOLE'}

    # save the current area
    area = bpy.context.area.type

    # try each type
    for type in types:
        # set the context
        bpy.context.area.type = type

        # print out context where operator works (change the ops below to check a different operator)
        if bpy.ops.sequencer.duplicate.poll():
            print(type)

    # leave the context where it was
    bpy.context.area.type = area


@dump_args
def set_context_to_graph_editor(context=None):
    if context is None:
        context = bpy.context
    graph_area = [context.screen.areas[k] for k in range(len(context.screen.areas)) if
                  context.screen.areas[k].type == 'GRAPH_EDITOR'][0]
    graph_window_region = [graph_area.regions[k] for k in range(len(graph_area.regions)) if
                           graph_area.regions[k].type == 'WINDOW'][0]
    c = context.copy()
    c['area'] = graph_area
    c['region'] = graph_window_region


def get_n_jobs(n_jobs):
    import multiprocessing
    cpu_num = multiprocessing.cpu_count()
    n_jobs = int(n_jobs)
    if n_jobs > cpu_num:
        n_jobs = cpu_num
    elif n_jobs < 0:
        n_jobs = cpu_num + n_jobs
    return n_jobs


def get_args_list(val):
    val = val.replace("'", '')
    if ',' in val:
        ret = val.split(',')
    elif len(val) == 0:
        ret = []
    else:
        ret = [val]
    return ret


def get_hemi_delim_and_pos(label_name):
    delim, pos, label, label_hemi = '', '', label_name, ''
    for hemi in ['rh', 'lh']:
        if label_name.startswith('{}-'.format(hemi)):
            delim, pos, label = '-', 'start', label_name[3:]
            label_hemi = hemi
            break
        if label_name.startswith('{}_'.format(hemi)):
            delim, pos, label = '_', 'start', label_name[3:]
            label_hemi = hemi
            break
        if label_name.startswith('{}.'.format(hemi)):
            delim, pos, label = '.', 'start', label_name[3:]
            label_hemi = hemi
            break
        if label_name.endswith('-{}'.format(hemi)):
            delim, pos, label = '-', 'end', label_name[:-3]
            label_hemi = hemi
            break
        if label_name.endswith('_{}'.format(hemi)):
            delim, pos, label = '_', 'end', label_name[:-3]
            label_hemi = hemi
            break
        if label_name.endswith('.{}'.format(hemi)):
            label_hemi = hemi
            delim, pos, label = '.', 'end', label_name[:-3]
            break
    return delim, pos, label, label_hemi


def get_hemi_from_fname(fname):
    _, _, _, hemi = get_hemi_delim_and_pos(fname)
    return hemi


def get_label_hemi_invariant_name(label_name):
    _, _, label_inv_name, _ = get_hemi_delim_and_pos(label_name)
    while label_inv_name != label_name:
        label_name = label_inv_name
        _, _, label_inv_name, _ = get_hemi_delim_and_pos(label_name)
    return label_inv_name


def get_hemi_from_full_fname(fname):
    folder = namebase(fname)
    hemi = get_hemi_from_fname(folder)
    while hemi == '' and folder != '':
        fname = get_parent_fol(fname)
        folder = fname.split(op.sep)[-1]
        hemi = get_hemi_from_fname(folder)
    return hemi


def get_label_for_full_fname(fname, delim='-'):
    fname_file_type = file_type(fname)
    names = [get_label_hemi_invariant_name(namebase(fname))]
    folder = namebase(fname)
    hemi = get_hemi_from_fname(folder)
    while hemi == '' and folder != '':
        fname = get_parent_fol(fname)
        folder = fname.split(op.sep)[-1]
        names.insert(0, get_label_hemi_invariant_name(folder))
        hemi = get_hemi_from_fname(folder)
    return '{}.{}.{}'.format(delim.join(names), hemi, fname_file_type)


def get_both_hemis_files(fname):
    hemi = get_hemi_from_fname(namebase(fname))
    full_fname = fname
    if hemi != '':
        other_hemi_fname = op.join(get_parent_fol(fname), get_other_hemi_label_name(fname))
    else:
        folder = get_parent_fol(fname)
        while hemi == '' and folder != '':
            fname = get_parent_fol(fname)
            folder = fname.split(op.sep)[-1]
            hemi = get_hemi_from_fname(folder)
        other_hemi_fname = full_fname.replace(folder, get_other_hemi_label_name(folder))
    return {hemi: full_fname, other_hemi(hemi): other_hemi_fname}


def get_other_hemi_label_name(label_name):
    add_file_type = False
    delim, pos, label, hemi = get_hemi_delim_and_pos(label_name)
    if hemi == '':
        delim, pos, label, hemi = get_hemi_delim_and_pos(namebase(label_name))
        add_file_type = True
    if hemi == '':
        print("Can't find the hemi in {}!".format(label_name))
        return ''
    else:
        other_hemi = 'rh' if hemi == 'lh' else 'lh'
        other_hemi_fname = build_label_name(delim, pos, label, other_hemi)
        if add_file_type:
            other_hemi_fname = '{}.{}'.format(other_hemi_fname, file_type(label_name))
        return other_hemi_fname


def get_template_hemi_label_name(label_name, wild_char=False):
    add_file_type = False
    delim, pos, label, hemi = get_hemi_delim_and_pos(label_name)
    if hemi == '':
        delim, pos, label, hemi = get_hemi_delim_and_pos(namebase(label_name))
        add_file_type = True
    hemi_temp = '?h' if wild_char else '{hemi}'
    res_label_name = build_label_name(delim, pos, label, hemi_temp)
    if add_file_type:
        res_label_name = '{}.{}'.format(res_label_name, file_type(label_name))
    return res_label_name


def build_label_name(delim, pos, label, hemi):
    if pos == 'end':
        return '{}{}{}'.format(label, delim, hemi)
    else:
        return '{}{}{}'.format(hemi, delim, label)


def min_stc_hemi(stc, hemi):
    if hemi == 'rh':
        return np.min(stc.rh_data) if stc.rh_data.shape[0] > 0 else 0
    else:
        return np.min(stc.lh_data) if stc.lh_data.shape[0] > 0 else 0


def min_stc(stc):
    return min([min_stc_hemi(stc, hemi) for hemi in HEMIS])


def max_stc_hemi(stc, hemi):
    if hemi == 'rh':
        return np.max(stc.rh_data) if stc.rh_data.shape[0] > 0 else 0
    else:
        return np.max(stc.lh_data) if stc.lh_data.shape[0] > 0 else 0


def max_stc(stc):
    return max([max_stc_hemi(stc, hemi) for hemi in HEMIS])


def check_hemi(hemi):
    if hemi in HEMIS:
        hemi = [hemi]
    elif hemi=='both':
        hemi = HEMIS
    else:
        raise ValueError('wrong hemi value!')
    return hemi


if MNE_EXIST:
    class Label(mne.label.Label):
        pass
else:
    class Label(object):
        vertices, pos, values = [], [], []
        comment, hemi, name = '', '', ''

        def __init__(self, vertices, pos=None, values=None, hemi=None, comment='', name=None):
            self.name = name
            self.hemi = hemi
            self.vertices = vertices
            self.pos = pos
            self.values = values
            self.comment = comment


def read_label_file(label_fname):
    """Read FreeSurfer Label file.

    Parameters
    ----------
    filename : string
        Path to label file.

    Returns
    -------
    - ``vertices``: vertex indices (0 based, column 1)
    - ``pos``: locations in meters (columns 2 - 4 divided by 1000)
    - ``values``: values at the vertices (column 5)
    """
    # read the file
    with open(label_fname, 'r') as fid:
        comment = fid.readline().replace('\n', '')[1:]
        nv = int(fid.readline())
        data = np.empty((5, nv))
        for i, line in enumerate(fid):
            data[:, i] = line.split()

    # let's make sure everything is ordered correctly
    vertices = np.array(data[0], dtype=np.int32)
    pos = 1e-3 * data[1:4].T
    values = data[4]
    order = np.argsort(vertices)
    vertices = vertices[order]
    pos = pos[order]
    values = values[order]
    _, _, label, hemi = get_hemi_delim_and_pos(namebase(label_fname))
    name = '{}-{}'.format(label, hemi)
    return Label(vertices, pos, values, hemi, name=name)


def read_labels_from_annots(subject, subjects_dir, atlas, hemi='both'):
    labels = []
    for hemi in check_hemi(hemi):
        hemi_annot_fname = op.join(subjects_dir, subject, 'label', '{}.{}.annot'.format(hemi, atlas))
        labels.extend(read_labels_from_annot(hemi_annot_fname))
    return sorted(labels, key=lambda l: l.name)


def read_labels_from_annot(annot_fname):
    """Read labels from a FreeSurfer annotation file.

    Note: Only cortical labels will be returned.

    Parameters
    ----------
    subject : str
        The subject for which to read the parcellation for.
    parc : str
        The parcellation to use, e.g., 'aparc' or 'aparc.a2009s'.
    hemi : str
        The hemisphere to read the parcellation for, can be 'lh', 'rh',
        or 'both'.
    surf_name : str
        Surface used to obtain vertex locations, e.g., 'white', 'pial'
    annot_fname : str or None
        Filename of the .annot file. If not None, only this file is read
        and 'parc' and 'hemi' are ignored.
    regexp : str
        Regular expression or substring to select particular labels from the
        parcellation. E.g. 'superior' will return all labels in which this
        substring is contained.
    subjects_dir : string, or None
        Path to SUBJECTS_DIR if it is not set in the environment.
    verbose : bool, str, int, or None
        If not None, override default verbose level (see :func:`mne.verbose`
        and :ref:`Logging documentation <tut_logging>` for more).

    Returns
    -------
    labels : list of Label
        The labels, sorted by label name (ascending).
    """
    labels = list()
    hemi = get_hemi_from_fname(namesbase_with_ext(annot_fname))
    annot, ctab, label_names = _read_annot(annot_fname)
    label_rgbas = ctab[:, :4]
    label_ids = ctab[:, -1]

    for label_id, label_name, label_rgba in zip(label_ids, label_names, label_rgbas):
        vertices = np.where(annot == label_id)[0]
        if len(vertices) == 0:
            # label is not part of cortical surface
            continue
        name = label_name.decode() + '-' + hemi
        # label = Label(name, hemi, vertices, [], [])
        label = Label(vertices, None, None, hemi, name=name)
        labels.append(label)

    # sort the labels by label name
    labels = sorted(labels, key=lambda l: l.name)
    return labels


def _read_annot(fname):
    """Read a Freesurfer annotation from a .annot file.

    Note : Copied from PySurfer

    Parameters
    ----------
    fname : str
        Path to annotation file

    Returns
    -------
    annot : numpy array, shape=(n_verts)
        Annotation id at each vertex
    ctab : numpy array, shape=(n_entries, 5)
        RGBA + label id colortable array
    names : list of str
        List of region names as stored in the annot file

    """
    with open(fname, "rb") as fid:
        n_verts = np.fromfile(fid, '>i4', 1)[0]
        data = np.fromfile(fid, '>i4', n_verts * 2).reshape(n_verts, 2)
        annot = data[data[:, 0], 1]
        ctab_exists = np.fromfile(fid, '>i4', 1)[0]
        if not ctab_exists:
            raise Exception('Color table not found in annotation file')
        n_entries = np.fromfile(fid, '>i4', 1)[0]
        if n_entries > 0:
            length = np.fromfile(fid, '>i4', 1)[0]
            # orig_tab = np.fromfile(fid, '>c', length)
            # orig_tab = orig_tab[:-1]

            names = list()
            ctab = np.zeros((n_entries, 5), np.int)
            for i in range(n_entries):
                name_length = np.fromfile(fid, '>i4', 1)[0]
                name = np.fromfile(fid, "|S%d" % name_length, 1)[0]
                names.append(name)
                ctab[i, :4] = np.fromfile(fid, '>i4', 4)
                ctab[i, 4] = (ctab[i, 0] + ctab[i, 1] * (2 ** 8) +
                              ctab[i, 2] * (2 ** 16) +
                              ctab[i, 3] * (2 ** 24))
        else:
            ctab_version = -n_entries
            if ctab_version != 2:
                raise Exception('Color table version not supported')
            n_entries = np.fromfile(fid, '>i4', 1)[0]
            ctab = np.zeros((n_entries, 5), np.int)
            length = np.fromfile(fid, '>i4', 1)[0]
            np.fromfile(fid, "|S%d" % length, 1)  # Orig table path
            entries_to_read = np.fromfile(fid, '>i4', 1)[0]
            names = list()
            for i in range(entries_to_read):
                np.fromfile(fid, '>i4', 1)  # Structure
                name_length = np.fromfile(fid, '>i4', 1)[0]
                name = np.fromfile(fid, "|S%d" % name_length, 1)[0]
                names.append(name)
                ctab[i, :4] = np.fromfile(fid, '>i4', 4)
                ctab[i, 4] = (ctab[i, 0] + ctab[i, 1] * (2 ** 8) +
                              ctab[i, 2] * (2 ** 16))

        # convert to more common alpha value
        ctab[:, 3] = 255 - ctab[:, 3]

    return annot, ctab, names


def create_labels_contours():
    subject, atlas = get_user(), bpy.context.scene.subject_annot_files
    cmd = '{} -m src.preproc.anatomy -s {} -a {} -f create_spatial_connectivity,calc_labeles_contours'.format(
        bpy.context.scene.python_cmd, subject, atlas)
    run_command_in_new_thread(cmd, False)


def make_link(source, target, overwrite=False):
    try:
        os.symlink(source, target)
        return True
    except FileExistsError as e:
        if not overwrite:
            print('{} already exist'.format(target))
        else:
            os.remove(target)
            os.symlink(source, target)
        return True
    except:
        return False


def both_hemi_files_exist(file_template):
    return op.isfile(file_template.format(hemi='rh')) and op.isfile(file_template.format(hemi='lh'))


def delete_files(temp):
    for fname in glob.glob(temp):
        os.remove(fname)


def print_traceback():
    import traceback
    print(''.join(traceback.format_stack()))


def file_modification_time(fname):
    from datetime import datetime
    try:
        mtime = os.path.getmtime(fname)
    except OSError:
        mtime = 0
    return datetime.fromtimestamp(mtime)


def apply_trans(trans, point):
    return np.dot(trans, np.append(point, 1))[:3]


def remove_file(fname, raise_error_if_does_not_exist=False):
    try:
        if op.isfile(fname):
            os.remove(fname)
    except:
        if raise_error_if_does_not_exist:
            raise Exception(traceback.format_exc())
        else:
            print(traceback.format_exc())