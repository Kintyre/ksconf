""" SUBCOMMAND:  ``ksconf filter <CONF>``

Usage example:

.. code-block:: sh

    ksconf filter default/savedsearches.conf --stanza "My Special Search" -o my-special-search.conf

Future things to support:

 * SED-like rewriting for stanza name or key values.
 * Mini eval/query language for simple data manipulations supporting mixed used of matching modes
   on a case-by-base basis, custom logic (AND,OR,arbitrary groups), projections, and content
   rewriting.  (Should leverage custom 'combine' mini-language where possible.)

"""

from __future__ import absolute_import, unicode_literals

import argparse
import sys

from ksconf.commands import ConfFileType, KsconfCmd, dedent
from ksconf.conf.parser import PARSECONF_MID_NC, write_conf_stream
from ksconf.consts import EXIT_CODE_SUCCESS
from ksconf.filter import FilteredList, FilteredListWildcard, create_filtered_list
from ksconf.util.completers import conf_files_completer


class FilterCmd(KsconfCmd):
    help = "A stanza-aware GREP tool for conf files"
    description = dedent("""
    Filter the contents of a conf file in various ways.  Stanzas can be included
    or excluded based on a provided filter or based on the presence or value of a key.

    Where possible, this command supports GREP-like arguments to bring a familiar feel.
    """)

    # format = "manual"
    maturity = "alpha"

    def __init__(self, *args, **kwargs):
        super(FilterCmd, self).__init__(*args, **kwargs)
        self.stanza_filters = None
        self.attr_presence_filters = None

    def register_args(self, parser):
        # type: (argparse.ArgumentParser) -> None
        parser.add_argument("conf", metavar="CONF", help="Input conf file", nargs="+",
                            type=ConfFileType("r", parse_profile=PARSECONF_MID_NC)
                            ).completer = conf_files_completer
        parser.add_argument("-o", "--output", metavar="FILE",
                            type=argparse.FileType('w'), default=self.stdout,
                            help="File where the filtered results are written.  "
                                 "Defaults to standard out.")
        parser.add_argument("--comments", "-C",
                            action="store_true", default=False,
                            help="Preserve comments.  Comments are discarded by default.")
        parser.add_argument("--verbose", action="store_true", default=False,
                            help="Enable additional output.")

        parser.add_argument("--match", "-m",  # metavar="MODE",
                            choices=["regex", "wildcard", "string"],
                            default="wildcard",
                            help=dedent("""\
            Specify pattern matching mode.
            Defaults to 'wildcard' allowing for ``*`` and  ``?`` matching.
            Use 'regex' for more power but watch out for shell escaping.
            Use 'string' to enable literal matching."""))
        parser.add_argument("--ignore-case", "-i", action="store_true",
                            help=dedent("""\
            Ignore case when comparing or matching strings.
            By default matches are case-sensitive."""))
        parser.add_argument("--invert-match", "-v", action="store_true",
                            help=dedent("""\
            Invert match results.
            This can be used to show what content does NOT match,
            or make a backup copy of excluded content."""))

        pg_out = parser.add_argument_group("Output mode", dedent("""\
            Select an alternate output mode.
            If any of the following options are used, the stanza output is not shown.
            """))
        pg_out.add_argument("--files-with-matches", "-l", action="store_true",
                            help="List files that match the given search criteria")
        pg_om1 = pg_out.add_mutually_exclusive_group()
        pg_om1.add_argument("--count", "-c", action="store_true",
                            help="Count matching stanzas")
        pg_om1.add_argument("--brief", "-b", action="store_true",
                            help="List name of matching stanzas")

        pg_sel = parser.add_argument_group("Stanza selection", dedent("""\
            Include or exclude entire stanzas using these filter options.

            All filter options can be provided multiple times.
            If you have a long list of filters, they can be saved in a file and referenced using
            the special ``file://`` prefix.  One entry per line."""))

        pg_sel.add_argument("--stanza", metavar="PATTERN", action="append", default=[],
                            help=dedent("""
            Match any stanza who's name matches the given pattern.
            PATTERN supports bulk patterns via the ``file://`` prefix."""))

        pg_sel.add_argument("--attr-present", metavar="ATTR", action="append", default=[],
                            help=dedent("""\
            Match any stanza that includes the ATTR attribute.
            ATTR supports bulk attribute patterns via the ``file://`` prefix."""))

        '''# Add next
        pg_sel.add_argument("--attr-eq", metavar=("ATTR", "PATTERN"), nargs=2, action="append",
                            default=[],
                            help="""
            Match any stanza that includes an attribute matching the pattern.
            PATTERN supports the special ``file://filename`` syntax.""")
        '''
        ''' # This will be more difficult
        pg_sel.add_argument("--attr-ne",  metavar=("ATTR", "PATTERN"), nargs=2, action="append",
                            default=[],
                            help="""
            Match any stanza that includes an attribute matching the pattern.
            PATTERN supports the special ``file://`` syntax.""")
        '''

        pg_con = parser.add_argument_group("Attribute selection", dedent("""\
            Include or exclude attributes passed through.
            By default, all attributes are preserved.
            Allowlist (keep) operations are preformed before blocklist (reject) operations."""))

        pg_con.add_argument("--keep-attrs", metavar="WC-ATTR", default=[], action="append",
                            help=dedent("""\
            Select which attribute(s) will be preserved.
            This space separated list of attributes indicates what to preserve.
            Supports wildcards."""))

        pg_con.add_argument("--reject-attrs", metavar="WC-ATTR", default=[], action="append",
                            help=dedent("""\
            Select which attribute(s) will be discarded.
            This space separated list of attributes indicates what to discard.
            Supports wildcards."""))

    def prep_filters(self, args):
        flags = 0
        if args.ignore_case:
            flags |= FilteredList.IGNORECASE
        if args.verbose:
            flags |= FilteredList.VERBOSE

        self.stanza_filters = create_filtered_list(args.match, flags).feedall(args.stanza)
        self.attr_presence_filters = create_filtered_list(args.match, flags)
        self.attr_presence_filters.feedall(args.attr_present)

        if args.keep_attrs or args.reject_attrs:
            self.attrs_keep_filter = FilteredListWildcard(flags)
            for attrs in args.keep_attrs:
                self.attrs_keep_filter.feedall(attrs.split(" "))
            self.attrs_reject_filter = FilteredListWildcard(FilteredList.INVERT | flags)
            for attrs in args.reject_attrs:
                self.attrs_reject_filter.feedall(attrs.split(" "))
        else:
            # Bypass filter
            self.filter_attrs = lambda x: x

    def _test_stanza(self, stanza, attributes):
        if self.stanza_filters.match_stanza(stanza):
            # If there are no attribute level filters, automatically keep (preserves empty stanzas)
            if not self.attr_presence_filters.has_rules:
                return True
            # See if any of the attributes we are looking for exist, if so keep the entire stanza
            for attr in attributes:
                if self.attr_presence_filters.match(attr):
                    return True
        return False

    def filter_attrs(self, content):
        d = {}
        for (attr, value) in content.items():
            if self.attrs_keep_filter.match(attr) and self.attrs_reject_filter.match(attr):
                d[attr] = content[attr]
        return d

    def output(self, args, matches, filename):
        if args.files_with_matches:
            if matches:
                if args.count:
                    args.output.write("{} has {} matching stanza(s)\n".format(filename, len(matches)))
                elif args.brief:
                    for stanza_name in matches:
                        args.output.write("{}: {}\n".format(filename, stanza_name))
                else:
                    # Just show a single file
                    args.output.write("{}\n".format(filename))
            elif args.verbose:
                self.stderr.write("No matching stanzas in {}\n".format(filename))
        elif args.count:
            args.output.write("{}\n".format(len(matches)))
        elif args.brief:
            for stanza_name in matches:
                args.output.write("{}\n".format(stanza_name))
        else:
            if len(args.conf) > 1:
                args.output.write("#  {}\n".format(filename))
            if matches:
                write_conf_stream(args.output, matches)
            elif args.verbose:
                self.stderr.write("No matching stanzas in {}\n".format(filename))
            if args.verbose:
                sys.stderr.write("Matched {} stanzas from {}\n".format(len(matches), filename))

    def run(self, args):
        ''' Filter configuration files. '''
        self.prep_filters(args)

        # By allowing multiple input CONF files, this means that we could have duplicate stanzas
        # (not detected by the parser)
        # so for now that just means duplicate stanzas on the output, but that may be problematic
        # I guess this is really up to the invoker to know if they care about that or not...
        # Still would be helpful for a quick "grep" of a large number of files

        for conf in args.conf:
            conf.set_parser_option(keep_comments=args.comments)
            cfg = conf.data
            # Should this be an ordered dict?
            cfg_out = dict()
            for stanza_name, attributes in cfg.items():
                keep = self._test_stanza(stanza_name, attributes) ^ args.invert_match
                if keep:
                    cfg_out[stanza_name] = self.filter_attrs(attributes)

            self.output(args, cfg_out, conf.name)
            # Explicit flush used to resolve a CLI unittest timing issue in pypy
            args.output.flush()

        return EXIT_CODE_SUCCESS
