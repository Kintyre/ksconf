"""
SUBCOMMAND:  ``ksconf merge --target=<CONF> <CONF> [ <CONF-n> ... ]``

Usage example:

.. code-block:: sh

    ksconf merge --target=master-props.conf /opt/splunk/etc/apps/*TA*/{default,local}/props.conf

"""
from __future__ import absolute_import, unicode_literals

import os

from ksconf.commands import ConfFileProxy, ConfFileType, KsconfCmd, dedent
from ksconf.conf.merge import merge_conf_files
from ksconf.conf.parser import PARSECONF_MID, PARSECONF_STRICT
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer


class MergeCmd(KsconfCmd):
    help = "Merge two or more .conf files"
    description = dedent("""\
    Merge two or more .conf files into a single combined .conf file.
    This is similar to the way that Splunk logically combines the ``default`` and ``local``
    folders at runtime.
    """)
    maturity = "stable"

    def register_args(self, parser):
        parser.add_argument("conf", metavar="FILE", nargs="+",
                            help="The source configuration file(s) to collect settings from."
                            ).completer = conf_files_completer
        parser.add_argument("--target", "-t", metavar="FILE",
                            type=ConfFileType("r+", "none", parse_profile=PARSECONF_STRICT),
                            default=ConfFileProxy("<stdout>", "w", self.stdout), help=dedent("""\
            Save the merged configuration files to this target file.
            If not provided, the merged conf is written to standard output.""")
                            ).completer = conf_files_completer

        # This is helpful when writing bash expressions like MyApp/{default,local}/props.conf;
        # when either default or local may not be present.
        parser.add_argument("--ignore-missing", "-s", default=False, action="store_true",
                            help="Silently ignore any missing CONF files.")

        parser.add_argument("--dry-run", "-D", default=False, action="store_true", help=dedent("""\
            Enable dry-run mode.
            Instead of writing to TARGET, preview changes in 'diff' format.
            If TARGET doesn't exist, then show the merged file."""))
        parser.add_argument("--banner", "-b", default="", help=dedent("""\
            A banner or warning comment added to the top of the TARGET file.
            Used to discourage Splunk admins from editing an auto-generated file."""))

    def run(self, args):
        ''' Merge multiple configuration files into one '''
        self.parse_profile = PARSECONF_MID

        if args.ignore_missing:
            cfgs = [self.parse_conf(c) for c in args.conf if os.path.isfile(c) or c == "-"]
        else:
            cfgs = [self.parse_conf(conf) for conf in args.conf]

        merge_conf_files(args.target, cfgs, dry_run=args.dry_run,
                         banner_comment=args.banner)
        return EXIT_CODE_SUCCESS
