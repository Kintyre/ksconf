""" SUBCOMMAND:  ksconf sort <CONF>

Usage example:  To recursively sort all files (in-place):

    find . -name '*.conf' | xargs ksconf sort -i

"""
from __future__ import absolute_import, unicode_literals

from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.parser import parse_conf, PARSECONF_STRICT, smart_write_conf, write_conf, \
    ConfParserException
from ksconf.consts import SMART_NOCHANGE, EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_SORT_APPLIED, \
    EXIT_CODE_SUCCESS
from ksconf.util.completers import conf_files_completer


def _has_nosort_marker(path):
    # KISS:  Look for the KSCONF-NO-SORT string in the first 4k of this file.
    with open(path, "rb") as stream:
        prefix = stream.read(4096)
    return b"KSCONF-NO-SORT" in prefix


class SortCmd(KsconfCmd):
    help = "Sort a Splunk .conf file creating a normalized format appropriate for version control"
    description = dedent("""\
    Sort a Splunk .conf file.  Sort has two modes:  (1) by default, the sorted
    config file will be echoed to the screen.  (2) the config files are updated
    in-place when the -i' option is used.

    Manually managed conf files can be blacklisted by add a comment containing the
    string ``KSCONF-NO-SORT`` to the top of any .conf file.
    """)
    format = "manual"
    maturity = "stable"

    def register_args(self, parser):
        import argparse
        parser.add_argument("conf", metavar="FILE", nargs="+",
                            type=argparse.FileType('r'), default=[self.stdin],
                            help="Input file to sort, or standard input."
                            ).completer = conf_files_completer

        # Pick mode:  target (sysout) vs inplace
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--target", "-t", metavar="FILE",
                          type=argparse.FileType('w'), default=self.stdout,
                          help="File to write results to.  Defaults to standard output."
                          ).completer = conf_files_completer
        mode.add_argument("--inplace", "-i",
                          action="store_true", default=False, help=dedent("""\
                          Replace the input file with a sorted version.
                          Warning this a potentially destructive operation that may
                          move/remove comments."""))

        # Inplace update arguments
        grp1 = parser.add_argument_group("In-place update arguments")
        grp1.add_argument("-F", "--force", action="store_true",
                          help=dedent("""\
                          Force file sorting for all files, even for files containing the special
                          'KSCONF-NO-SORT' marker."""))
        grp1.add_argument("-q", "--quiet", action="store_true",
                          help=dedent("""\
                          Reduce the output.
                          Reports only updated or invalid files.
                          This is useful for pre-commit hooks, for example."""))

        parser.add_argument("-n", "--newlines", metavar="LINES", type=int, default=1,
                            help="Lines between stanzas.")


    def run(self, args):
        ''' Sort one or more configuration file. '''
        stanza_delims = "\n" * args.newlines
        if args.inplace:
            failure = False
            changes = 0
            for conf in args.conf:
                try:
                    if not args.force and _has_nosort_marker(conf.name):
                        if not args.quiet:
                            self.stderr.write("Skipping blacklisted file {}\n".format(conf.name))
                        continue
                    data = parse_conf(conf, profile=PARSECONF_STRICT)
                    conf.close()
                    smart_rc = smart_write_conf(conf.name, data, stanza_delim=stanza_delims,
                                                sort=True)
                except ConfParserException as e:
                    smart_rc = None
                    self.stderr.write("Error trying to process file {0}.  "
                                      "Error:  {1}\n".format(conf.name, e))
                    failure = True
                if smart_rc == SMART_NOCHANGE:
                    if not args.quiet:
                        self.stderr.write("Nothing to update.  "
                                          "File {0} is already sorted\n".format(conf.name))
                else:
                    self.stderr.write("Replaced file {0} with sorted content.\n".format(conf.name))
                    changes += 1
            if failure:
                return EXIT_CODE_BAD_CONF_FILE
            if changes:
                return EXIT_CODE_SORT_APPLIED
        else:
            for conf in args.conf:
                if len(args.conf) > 1:
                    args.target.write("---------------- [ {0} ] ----------------\n\n"
                                      .format(conf.name))
                try:
                    data = parse_conf(conf, profile=PARSECONF_STRICT)
                    write_conf(args.target, data, stanza_delim=stanza_delims, sort=True)
                except ConfParserException as e:
                    self.stderr.write("Error trying processing {0}.  Error:  {1}\n".
                                      format(conf.name, e))
                    return EXIT_CODE_BAD_CONF_FILE
            return EXIT_CODE_SUCCESS
