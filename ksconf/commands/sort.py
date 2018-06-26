import sys

from ksconf.conf.parser import parse_conf, PARSECONF_STRICT, smart_write_conf, ConfParserException, \
    write_conf
from ksconf.consts import SMART_NOCHANGE, EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_SORT_APPLIED


def _has_nosort_marker(path):
    # KISS:  Look for the KSCONF-NO-SORT string in the first 4k of this file.
    with open(path, "rb") as stream:
        prefix = stream.read(4096)
    return b"KSCONF-NO-SORT" in prefix


def do_sort(args):
    ''' Sort a single configuration file. '''
    stanza_delims = "\n" * args.newlines
    if args.inplace:
        failure = False
        changes = 0
        for conf in args.conf:
            try:
                if not args.force and _has_nosort_marker(conf.name):
                    if not args.quiet:
                        sys.stderr.write("Skipping blacklisted file {}\n".format(conf.name))
                    continue
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                conf.close()
                smart_rc = smart_write_conf(conf.name, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                smart_rc = None
                sys.stderr.write("Error trying to process file {0}.  "
                                 "Error:  {1}\n".format(conf.name, e))
                failure = True
            if smart_rc == SMART_NOCHANGE:
                if not args.quiet:
                    sys.stderr.write("Nothing to update.  "
                                     "File {0} is already sorted\n".format(conf.name))
            else:
                sys.stderr.write("Replaced file {0} with sorted content.\n".format(conf.name))
                changes += 1
        if failure:
            return EXIT_CODE_BAD_CONF_FILE
        if changes:
            return EXIT_CODE_SORT_APPLIED
    else:
        for conf in args.conf:
            if len(args.conf) > 1:
                args.target.write("---------------- [ {0} ] ----------------\n\n".format(conf.name))
            try:
                data = parse_conf(conf, profile=PARSECONF_STRICT)
                write_conf(args.target, data, stanza_delim=stanza_delims, sort=True)
            except ConfParserException, e:
                sys.stderr.write("Error trying processing {0}.  Error:  {1}\n".format(conf.name, e))
                return EXIT_CODE_BAD_CONF_FILE
