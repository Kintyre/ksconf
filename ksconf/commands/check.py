""" SUBCOMMAND:  ``ksconf check <CONF>``

Usage example:   (Nice pre-commit script)

.. code-block:: sh

    find . -name '*.conf' | ksconf check -

"""
from __future__ import absolute_import, unicode_literals

import os
from collections import Counter

from ksconf.command import KsconfCmd, dedent
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
                self.stderr.write(f"Skipping missing file:  {conf}\n")
                c["missing"] += 1
                continue
            try:
                parse_conf(conf, profile=PARSECONF_STRICT_NC)
                c["okay"] += 1
                if not args.quiet:
                    self.stdout.write(f"Successfully parsed {conf}\n")
                    self.stdout.flush()
            except ConfParserException as e:
                self.stderr.write(f"Error in file {conf}:  {e}\n")
                self.stderr.flush()
                exit_code = EXIT_CODE_BAD_CONF_FILE
                # TODO:  Break out counts by error type/category (there's only a few of them)
                c["error"] += 1
            except Exception as e:  # pragma: no cover
                self.stderr.write(f"Unhandled top-level exception while parsing {conf}.  "
                                  f"Aborting.\n{e}\n")
                debug_traceback()
                exit_code = EXIT_CODE_INTERNAL_ERROR
                c["error"] += 1
                break
        if True:  # show stats or verbose
            self.stdout.write(f"Completed checking {c['checked']} files.  "
                              f"rc={exit_code} Breakdown:\n"
                              f"   {c['okay']} files were parsed successfully.\n"
                              f"   {c['error']} files failed.\n")
        return exit_code
