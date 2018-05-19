import sys

from ksconf.conf.delta import compare_cfgs, show_diff
from ksconf.consts import EXIT_CODE_DIFF_EQUAL, EXIT_CODE_DIFF_NO_COMMON


def do_diff(args):
    ''' Compare two configuration files. '''
    args.conf1.set_parser_option(keep_comments=args.comments)
    args.conf2.set_parser_option(keep_comments=args.comments)

    cfg1 = args.conf1.data
    cfg2 = args.conf2.data

    diffs = compare_cfgs(cfg1, cfg2)
    rc = show_diff(args.output, diffs, headers=(args.conf1.name, args.conf2.name))
    if rc == EXIT_CODE_DIFF_EQUAL:
        sys.stderr.write("Files are the same.\n")
    elif rc == EXIT_CODE_DIFF_NO_COMMON:
        sys.stderr.write("No common stanzas between files.\n")
    return rc
