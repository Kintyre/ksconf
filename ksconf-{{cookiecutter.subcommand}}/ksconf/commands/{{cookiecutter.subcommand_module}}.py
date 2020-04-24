""" SUBCOMMAND:  ksconf {{ cookiecutter.subcommand }} <CONF> <CONF>

Usage example:

    ksconf {{ cookiecutter.subcommand }} default/props.conf local/props.conf

"""
from __future__ import absolute_import, unicode_literals

import argparse

from ksconf.commands import KsconfCmd, dedent, ConfFileType
from ksconf.conf.delta import compare_cfgs, show_diff
from ksconf.conf.parser import PARSECONF_MID_NC
from ksconf.consts import EXIT_CODE_DIFF_EQUAL, EXIT_CODE_DIFF_NO_COMMON
from ksconf.util.completers import conf_files_completer


class {{ cookiecutter.subcommand_class }}(KsconfCmd):
    help = "{{ cookiecutter.short_description }}"
    description = dedent("""\
    {{ cookiecutter.short_description }}

    A longer description of what the {{ cookiecutter.subcommand }} command does....

    Another paragraph.

    If you want to word-wrap this yourself, use ``format=manual``.
    """)
    format = "{{cookiecutter.docs_format}}"
    maturity = "{{cookiecutter.maturity}}"

    def register_args(self, parser):
        parser.add_argument("conf1", metavar="CONF1", help="Left side of the comparison",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                            ).completer = conf_files_completer
        parser.add_argument("conf2", metavar="CONF2", help="Right side of the comparison",
                            type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                            ).completer = conf_files_completer
        parser.add_argument("-o", "--output", metavar="FILE",
                            type=argparse.FileType('w'), default=self.stdout,
                            help="File where difference is stored.  Defaults to standard out.")
        parser.add_argument("--comments", "-C",
                            action="store_true", default=False,
                            help="Enable comparison of comments.  (Unlikely to work consistently)")

    def run(self, args):
        ''' {{cookiecutter.short_description}} '''
        args.conf1.set_parser_option(keep_comments=args.comments)
        args.conf2.set_parser_option(keep_comments=args.comments)

        cfg1 = args.conf1.data
        cfg2 = args.conf2.data

        diffs = compare_cfgs(cfg1, cfg2)
        rc = show_diff(args.output, diffs, headers=(args.conf1.name, args.conf2.name))
        if rc == EXIT_CODE_DIFF_EQUAL:
            self.stderr.write("Files are the same.\n")
        elif rc == EXIT_CODE_DIFF_NO_COMMON:
            self.stderr.write("No common stanzas between files.\n")
        return rc
