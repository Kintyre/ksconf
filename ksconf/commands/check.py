import os
import sys
from collections import Counter

from ksconf.conf.parser import parse_conf, PARSECONF_STRICT_NC, ConfParserException
from ksconf.consts import EXIT_CODE_SUCCESS, EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_INTERNAL_ERROR
from ksconf.util.file import _stdin_iter


def do_check(args):
    # Should we read a list of conf files from STDIN?
    if len(args.conf) == 1 and args.conf[0] == "-":
        confs = _stdin_iter()
    else:
        confs = args.conf
    c = Counter()
    exit_code = EXIT_CODE_SUCCESS
    for conf in confs:
        c["checked"] += 1
        if not os.path.isfile(conf):
            sys.stderr.write("Skipping missing file:  {0}\n".format(conf))
            c["missing"] += 1
            continue
        try:
            parse_conf(conf, profile=PARSECONF_STRICT_NC)
            c["okay"] += 1
            if not args.quiet:
                sys.stdout.write("Successfully parsed {0}\n".format(conf))
                sys.stdout.flush()
        except ConfParserException, e:
            sys.stderr.write("Error in file {0}:  {1}\n".format(conf, e))
            sys.stderr.flush()
            exit_code = EXIT_CODE_BAD_CONF_FILE
            # TODO:  Break out counts by error type/category (there's only a few of them)
            c["error"] += 1
        except Exception, e:  # pragma: no cover
            sys.stderr.write("Unhandled top-level exception while parsing {0}.  "
                             "Aborting.\n{1}\n".format(conf, e))
            exit_code = EXIT_CODE_INTERNAL_ERROR
            c["error"] += 1
            break
    if True:  # show stats or verbose
        sys.stdout.write("Completed checking {0[checked]} files.  rc={1} Breakdown:\n"
                         "   {0[okay]} files were parsed successfully.\n"
                         "   {0[error]} files failed.\n".format(c, exit_code))
    sys.exit(exit_code)
