# The setup suppose to run *before* installing python libs, so only python vanilla can be used here

import os
import os.path as op
import shutil
import traceback
from src.utils import setup_utils as utils
import glob

TITLE = 'MMVT Installation'
BLENDER_WIN_DIR = 'C:\Program Files\Blender Foundation\Blender'


def copy_resources_files(mmvt_root_dir, only_verbose=False):
    resource_dir = utils.get_resources_fol()
    utils.make_dir(op.join(op.join(mmvt_root_dir, 'color_maps')))
    files = ['aparc.DKTatlas40_groups.csv', 'atlas.csv', 'sub_cortical_codes.txt', 'FreeSurferColorLUT.txt',
             'empty_subject.blend']
    cm_files = glob.glob(op.join(resource_dir, 'color_maps', '*.npy'))
    all_files_exist = utils.all([op.isfile(op.join(mmvt_root_dir, file_name)) for file_name in files])
    all_cm_files_exist = utils.all([op.isfile(
        op.join(mmvt_root_dir, 'color_maps', '{}.npy'.format(utils.namebase(fname)))) for fname in cm_files])
    if all_files_exist and all_cm_files_exist:
        if only_verbose:
            print('All files exist!')
        return True
    if not all_cm_files_exist:
        for color_map_file in glob.glob(op.join(resource_dir, 'color_maps', '*.npy')):
            new_file_name = op.join(mmvt_root_dir, 'color_maps', color_map_file.split(op.sep)[-1])
            # print('Copy {} to {}'.format(color_map_file, new_file_name))
            if only_verbose:
                print('Coping {} to {}'.format(color_map_file, new_file_name))
            else:
                shutil.copy(color_map_file, new_file_name)
    if not all_files_exist:
        for file_name in files:
            if only_verbose:
                print('Copying {} to {}'.format(op.join(resource_dir, file_name), op.join(mmvt_root_dir, file_name)))
            else:
                shutil.copy(op.join(resource_dir, file_name), op.join(mmvt_root_dir, file_name))
    return utils.all([op.isfile(op.join(mmvt_root_dir, file_name)) for file_name in files])


def create_links(links_fol_name='links', gui=True, default_folders=False, only_verbose=False,
                 links_file_name='links.csv', overwrite=True):
    links_fol = utils.get_links_dir(links_fol_name)
    if only_verbose:
        print('making links dir {}'.format(links_fol))
    else:
        utils.make_dir(links_fol)
    links_names = ['blender', 'mmvt', 'subjects', 'eeg', 'meg', 'fMRI', 'electrodes']
    # if not utils.is_windows():
    #     links_names.insert(1, 'subjects')
    if not overwrite:
        all_links_exist = utils.all([utils.is_link(op.join(links_fol, link_name)) for link_name in links_names])
        if all_links_exist:
            print('All links exist!')
            links = {link_name:utils.get_link_dir(links_fol, link_name) for link_name in links_names}
            write_links_into_csv_file(links, links_fol, links_file_name)
            return True
    if not utils.is_windows() and not utils.is_link(op.join(links_fol, 'freesurfer')):
        if os.environ.get('FREESURFER_HOME', '') == '':
            print('If you are going to use FreeSurfer locally, please source it and rerun')
            cont = input("Do you want to continue (y/n)?") # If you choose to continue, you'll need to create a link to FreeSurfer manually")
            if cont.lower() != 'y':
                return
        else:
            freesurfer_fol = os.environ['FREESURFER_HOME']
            if not only_verbose:
                create_real_folder(freesurfer_fol)

    mmvt_message = 'Please select where do you want to put the blend files '
    subjects_message = 'Please select where do you want to store the FreeSurfer recon-all files neccessary for MMVT.\n' + \
              '(It is prefered to create a local folder, because MMVT is going to save files to this directory) '
    blender_message = 'Please select where did you install Blender '
    meg_message = 'Please select where do you want to put the MEG files (Cancel if you are not going to use MEG data) '
    eeg_message = 'Please select where do you want to put the EEG files (Cancel if you are not going to use EEG data) '
    fmri_message = 'Please select where do you want to put the fMRI files (Cancel if you are not going to use fMRI data) '
    electrodes_message = 'Please select where do you want to put the electrodes files (Cancel if you are not going to use electrodes data) '

    blender_fol = find_blender()
    if blender_fol != '':
        utils.create_folder_link(blender_fol, op.join(links_fol, 'blender'), overwrite)
    else:
        ask_and_create_link(links_fol, 'blender',  blender_message, gui, overwrite)
    default_message = "Would you like to set default links to the MMVT's folders?\n" + \
        "You can always change that later by running\n" + \
        "python -m src.setup -f create_links"
    create_default_folders = default_folders or mmvt_input(default_message, gui, 4) == 'Yes'

    messages = [mmvt_message, subjects_message, eeg_message, meg_message, fmri_message, electrodes_message]
    deafault_fol_names = ['mmvt_blend', 'subjects', 'eeg', 'meg', 'fMRI', 'electrodes']
    # if not utils.is_windows():
    #     messages.insert(0, subjects_message)
    create_default_dirs = [False] * 3 + [True] * 2 + [False] * 2

    links = {}
    if not only_verbose:
        for link_name, default_fol_name, message, create_default_dir in zip(
                links_names[1:], deafault_fol_names, messages, create_default_dirs):
            fol = ''
            if not create_default_folders:
                fol = ask_and_create_link(links_fol, link_name, message, gui, create_default_dir)
            if fol == '' or create_default_folders:
                fol = create_default_link(
                    links_fol, link_name, default_fol_name, create_default_dir, overwrite=overwrite)
                print('The "{}" link was created to {}'.format(link_name, fol))
            links[link_name] = fol

    links = get_all_links(links, links_fol)
    write_links_into_csv_file(links, links_fol, links_file_name)
    return utils.all([utils.is_link(op.join(links_fol, link_name)) for link_name in links_names])


def mmvt_input(message, gui, style=1):
    if gui:
        ret = utils.message_box(message, TITLE, style)
    else:
        ret = input(message)
    return ret


def ask_and_create_link(links_fol, link_name, message, gui=True, create_default_dir=False, overwrite=True):
    fol = ''
    if not overwrite and utils.is_link(op.join(links_fol, link_name)):
        fol = utils.get_link_dir(links_fol, link_name)
    else:
        choose_folder = mmvt_input(message, gui) == 'Ok'
        if choose_folder:
            root_fol = utils.get_parent_fol(links_fol)
            fol = utils.choose_folder_gui(root_fol, message) if gui else input()
            if fol != '':
                create_real_folder(fol)
                utils.create_folder_link(fol, op.join(links_fol, link_name))
                if create_default_dir:
                    utils.make_dir(op.join(fol, 'default'))
    return fol


def create_default_link(links_fol, link_name, default_fol_name, create_default_dir=False, overwrite=True):
    root_fol = utils.get_parent_fol(levels=3)
    fol = op.join(root_fol, default_fol_name)
    create_real_folder(fol)
    utils.create_folder_link(fol, op.join(links_fol, link_name), overwrite=overwrite)
    if create_default_dir:
        utils.make_dir(op.join(fol, 'default'))
    return fol


def get_all_links(links={}, links_fol=None, links_fol_name='links'):
    if links_fol is None:
        links_fol = utils.get_links_dir(links_fol_name)
    all_links = [utils.namebase(f) for f in glob.glob(op.join(links_fol, '*')) if utils.is_link(f)]
    all_links = {link_name:utils.get_link_dir(links_fol, link_name) for link_name in all_links if link_name not in links}
    links = utils.merge_two_dics(links, all_links)
    return links


def write_links_into_csv_file(links, links_fol=None, links_file_name='links.csv', links_fol_name='links'):
    import csv
    if links_fol is None:
        links_fol = utils.get_links_dir(links_fol_name)
    with open(op.join(links_fol, links_file_name), 'w') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',')
        for link_name, link_dir in links.items():
            csv_writer.writerow([link_name, link_dir])


def create_empty_links_csv(links_fol_name='links', links_file_name='links.csv'):
    links_fol = utils.get_links_dir(links_fol_name)
    links_names = ['mmvt', 'subjects', 'blender', 'eeg', 'meg', 'fMRI', 'electrodes']
    links = {link_name:'' for link_name in links_names}
    write_links_into_csv_file(links, links_fol, links_file_name)


def create_real_folder(real_fol):
    try:
        if real_fol == '':
            real_fol = utils.get_resources_fol()
        utils.make_dir(real_fol)
    except:
        print('Error with creating the folder "{}"'.format(real_fol))
        print(traceback.format_exc())


def install_reqs(only_verbose=False):
    import pip
    pip.main(['install', '--upgrade', 'pip'])
    retcode = 0
    reqs_fname = op.join(utils.get_parent_fol(levels=2), 'requirements.txt')
    with open(reqs_fname, 'r') as f:
        for line in f:
            if only_verbose:
                print('Trying to install {}'.format(line.strip()))
            else:
                pipcode = pip.main(['install', line.strip()])
                retcode = retcode or pipcode
    return retcode


def find_blender():
    blender_fol = ''
    if utils.is_windows():
        blender_win_fol = 'Program Files\Blender Foundation\Blender'
        if op.isdir(op.join('C:\\', blender_win_fol)):
            blender_fol = op.join('C:\\', blender_win_fol)
        elif op.isdir(op.join('D:\\', blender_win_fol)):
            blender_fol = op.join('D:\\', blender_win_fol)
    else:
        output = utils.run_script("find ~/ -name 'blender' -type d")
        if not isinstance(output, str):
            output = output.decode(sys.getfilesystemencoding(), 'ignore')
        blender_fols = output.split('\n')
        blender_fols = [fol for fol in blender_fols if op.isfile(op.join(
            utils.get_parent_fol(fol), 'blender.svg')) or 'blender.app' in fol]
        if len(blender_fols) == 1:
            blender_fol = utils.get_parent_fol(blender_fols[0])
        # if 'users' in sys.executable:
        #     path_split = sys.executable.split(op.sep)
        #     ind = path_split.index('users')
        #     root_path = op.sep.join(path_split[:ind+2])
        #     output = utils.run_script("find {} -name 'blender' -type d".format(root_path))
    return blender_fol


def create_fsaverage_link(links_fol_name='links'):
    freesurfer_home = os.environ.get('FREESURFER_HOME', '')
    if freesurfer_home != '':
        links_fol = utils.get_links_dir(links_fol_name)
        subjects_dir = utils.get_link_dir(links_fol, 'subjects', 'SUBJECTS_DIR')
        fsaverage_link = op.join(subjects_dir, 'fsaverage')
        if not utils.is_link(fsaverage_link):
            fsveareg_fol = op.join(freesurfer_home, 'subjects', 'fsaverage')
            utils.create_folder_link(fsveareg_fol, fsaverage_link)


def install_blender_reqs():
    # http://stackoverflow.com/questions/9956741/how-to-install-multiple-python-packages-at-once-using-pip
    try:
        blender_fol = utils.get_link_dir(utils.get_links_dir(), 'blender')
        resource_fol = utils.get_resources_fol()
        # Get pip
        blender_bin_fol = op.join(utils.get_parent_fol(blender_fol), 'Resources', '2.78', 'python', 'bin') if utils.is_osx() else \
            glob.glob(op.join(blender_fol, '2.7?', 'python'))[0]
        python_exe = 'python.exe' if utils.is_windows() else 'python3.5m'
        current_dir = os.getcwd()
        os.chdir(blender_bin_fol)
        # if utils.is_osx():
        cmd = '{} {}'.format(op.join('bin', python_exe), op.join(resource_fol, 'get-pip.py'))
        # elif utils.is_linux():
        #     cmd = '{} {}'.format(op.join(blender_bin_fol, 'python3.5m'), op.join(resource_fol, 'get-pip.py'))
        # else:
        #     print('No pizco for windows yet...')
        #     return
        utils.run_script(cmd)
        # install blender reqs:
        if not utils.is_windows():
            cmd = '{} install zmq pizco scipy mne joblib tqdm nibabel matplotlib'.format(op.join('bin', 'pip'))
            utils.run_script(cmd)
        else:
            print('Sorry, installing external python libs in python will be implemented in the future')
            # from src.mmvt_addon.scripts import install_blender_reqs
            # install_blender_reqs.wrap_blender_call(args.only_verbose)
        os.chdir(current_dir)
    except:
        print(traceback.format_exc())
        print("*** Can't install pizco ***")


def main(args):
    # 1) Install dependencies from requirements.txt (created using pipreqs)
    if utils.should_run(args, 'install_reqs'):
        install_reqs(args.only_verbose)

    # 2) Create links
    if utils.should_run(args, 'create_links'):
        links_created = create_links(args.links, args.gui, args.default_folders, args.only_verbose)
        if not links_created:
            print('Not all the links were created! Make sure all the links are created before running MMVT.')

    # 2,5) Create fsaverage folder link
    if utils.should_run(args, 'create_fsaverage_link'):
        create_fsaverage_link(args.links)

    # 3) Copy resources files
    if utils.should_run(args, 'copy_resources_files'):
        links_dir = utils.get_links_dir(args.links)
        mmvt_root_dir = utils.get_link_dir(links_dir, 'mmvt')
        resource_file_exist = copy_resources_files(mmvt_root_dir, args.only_verbose)
        if not resource_file_exist:
            input('Not all the resources files were copied to the MMVT folder ({}).\n'.format(mmvt_root_dir) +
                  'Please copy them manually from the mmvt_code/resources folder.\n' +
                  'Press any key to continue...')

    # 4) Install the addon in Blender (depends on resources and links)
    if utils.should_run(args, 'install_addon'):
        from src.mmvt_addon.scripts import install_addon
        install_addon.wrap_blender_call(args.only_verbose)

    # 5) Install python packages in Blender
    if utils.should_run(args, 'install_blender_reqs'):
        install_blender_reqs()

    if 'create_links_csv' in args.function:
        create_empty_links_csv()

    if 'create_csv' in args.function:
        write_links_into_csv_file(get_all_links())

    if 'find_blender' in args.function:
        find_blender()

    print('Finish!')


def print_help():
    str = '''
    Flags:
        -l: The links folder name (default: 'links')
        -g: Use GUI (True) or the command line (False) (default: True)
        -v: If True, just check the setup without doing anything (default: False)
        -d: If True, the script will create the default mmvt folders (default: True)
        -f: Set which function (or functions) you want to run (use commas witout spacing) (deafult: all):
            install_reqs, create_links, copy_resources_files, install_addon, install_blender_reqs, create_links_csv and create_csv
    '''
    print(str)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ['h', 'help', '-h', '-help']:
        print_help()
        exit()
    import argparse
    from src.utils import args_utils as au
    parser = argparse.ArgumentParser(description='MMVT Setup')
    parser.add_argument('-l', '--links', help='links folder name', required=False, default='links')
    parser.add_argument('-g', '--gui', help='choose folders using gui', required=False, default='1', type=au.is_true)
    parser.add_argument('-v', '--only_verbose', help='only verbose', required=False, default='0', type=au.is_true)
    parser.add_argument('-d', '--default_folders', help='default options', required=False, default='1', type=au.is_true)
    parser.add_argument('-f', '--function', help='functions to run', required=False, default='all', type=au.str_arr_type)
    args = utils.Bag(au.parse_parser(parser))
    main(args)
