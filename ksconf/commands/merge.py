from ksconf.conf.merge import merge_conf_files
from ksconf.consts import EXIT_CODE_SUCCESS


def do_merge(args):
    ''' Merge multiple configuration files into one '''
    merge_conf_files(args.target, args.conf, dry_run=args.dry_run, banner_comment=args.banner)
    return EXIT_CODE_SUCCESS
