import argparse
from src.preproc import meg_preproc as meg
from src.utils import utils
from src.utils import args_utils as au


def read_epoches_and_calc_activity(subject, mri_subject):
    args = meg.read_cmd_args(['-s', subject, '-m', mri_subject])
    args.function = ['calc_stc_per_condition', 'calc_labels_avg_per_condition', 'smooth_stc', 'save_activity_map']
    args.pick_ori = 'normal'
    args.colors_map = 'jet'
    meg.main(subject, mri_subject, args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MMVT')
    parser.add_argument('-s', '--subject', help='subject name', required=True, type=au.str_arr_type)
    parser.add_argument('-m', '--mri_subject', help='mri subject name', required=False, default=None,
                        type=au.str_arr_type)
    args = utils.Bag(au.parse_parser(parser))
    if not args.mri_subject:
        args.mri_subject = args.subject
    for subject, mri_subject in zip(args.subject, args.mri_subject):
        read_epoches_and_calc_activity(subject, mri_subject)