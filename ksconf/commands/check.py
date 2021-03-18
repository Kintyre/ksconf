""" SUBCOMMAND:  ``ksconf check <CONF>``

Usage example:   (Nice pre-commit script)

.. code-block:: sh

    find . -name '*.conf' | ksconf check -

"""
from __future__ import absolute_import, unicode_literals

import os
from collections import Counter

from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.parser import PARSECONF_STRICT_NC, ConfParserException, parse_conf
from ksconf.consts import EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_INTERNAL_ERROR, EXIT_CODE_SUCCESS
from ksconf.util import debug_traceback
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import _stdin_iter, expand_glob_list


class CheckCmd(KsconfCmd):
    help = "Perform basic syntax and sanity checks on .conf files"
    description = dedent("""
    Provides basic syntax and sanity checking for Splunk's .conf
    files.  Use Splunk's built-in ``btool check`` for a more robust
    validation of attributes and values.

    Consider using this utility as part of a pre-commit hook.""")
    maturity = "stable"

    def register_args(self, parser):
        parser.add_argument("conf", metavar="FILE", nargs="+", help=dedent("""\
            One or more configuration files to check.
            If '-' is given, then read a list of files to validate from standard input""")
                            ).completer = conf_files_completer
        parser.add_argument("--quiet", "-q", default=False, action="store_true",
                            help="Reduce the volume of output.")
        ''' # Do we really need this?
        parser.add_argument("--max-errors", metavar="INT", type=int, default=0, help=
            "Abort check if more than this many files fail validation.  "
            "Useful for a pre-commit hook where any failure is unacceptable.")
        '''

    def pre_run(self, args):
        # For Windows users, expand any glob patterns as needed.
        args.conf = list(expand_glob_list(args.conf))

    def run(self, args):
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
                self.stderr.write("Skipping missing file:  {0}\n".format(conf))
                c["missing"] += 1
                continue
            try:
                parse_conf(conf, profile=PARSECONF_STRICT_NC)
                c["okay"] += 1
                if not args.quiet:
                    self.stdout.write("Successfully parsed {0}\n".format(conf))
                    self.stdout.flush()
            except ConfParserException as e:
                self.stderr.write("Error in file {0}:  {1}\n".format(conf, e))
                self.stderr.flush()
                exit_code = EXIT_CODE_BAD_CONF_FILE
                # TODO:  Break out counts by error type/category (there's only a few of them)
                c["error"] += 1
            except Exception as e:  # pragma: no cover
                self.stderr.write("Unhandled top-level exception while parsing {0}.  "
                                  "Aborting.\n{1}\n".format(conf, e))
                debug_traceback()
                exit_code = EXIT_CODE_INTERNAL_ERROR
                c["error"] += 1
                break
        if True:  # show stats or verbose
            self.stdout.write("Completed checking {0[checked]} files.  rc={1} Breakdown:\n"
                              "   {0[okay]} files were parsed successfully.\n"
                              "   {0[error]} files failed.\n".format(c, exit_code))
        return exit_code
