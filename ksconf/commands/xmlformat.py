""" SUBCOMMAND:  ``ksconf xml-format <XML>``

Usage example:   (Nice pre-commit script)

.. code-block:: sh

    find default/data/ui -name '*.xml' | ksconf xml-format -

"""
from __future__ import absolute_import, unicode_literals

import os
from argparse import SUPPRESS
from collections import Counter

from ksconf.command import KsconfCmd, dedent
from ksconf.consts import (EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_FORMAT_APPLIED,
                           EXIT_CODE_INTERNAL_ERROR, EXIT_CODE_SUCCESS)
from ksconf.util import debug_traceback
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import _stdin_iter
# Main codebase is here:
from ksconf.xmlformat import SplunkSimpleXmlFormatter

# Lazy loaded by _handle_imports()
etree = None


class XmlFormatCmd(KsconfCmd):
    help = "Normalize XML view and nav files"
    description = dedent("""
    Normalize and apply consistent XML indentation and CDATA usage for XML dashboards and
    navigation files.

    Technically this could be used on *any* XML file, but certain element names specific to Splunk's
    simple XML dashboards are handled specially, and therefore could result in unusable results.

    The expected indentation level is guessed based on the first element indentation, but can be
    explicitly set if not detectable.
    """)
    maturity = "alpha"

    @classmethod
    def _handle_imports(cls):
        g = globals()
        if globals()["etree"]:
            return
        from lxml import etree
        cls.version_extra = f"lxml {etree.__version__}"
        g["etree"] = etree

    def register_args(self, parser):
        parser.add_argument("xml", metavar="FILE", nargs="+", help=dedent("""\
            One or more XML files to check.
            If '-' is given, then a list of files is read from standard input""")
                            ).completer = conf_files_completer
        parser.add_argument("--indent", type=int, default=2,
                            help="Number of spaces.  This is only used if indentation cannot be "
                            "guessed from the existing file.")
        parser.add_argument("--quiet", "-q", default=False, action="store_true",
                            help="Reduce the volume of output.")

        # Hidden arguments
        parser.add_argument("--disable-pre-commit-migration-check",
                            default=False, action="store_true", help=SUPPRESS)

    def pre_commit_repo_migration_warning(self, args):
        r"""
        Issue migration warning if (1) running hooks from the old repo (missing
        arg), and (2) parent process is from pre-commit (env var).


        Another workaround is to use:

        ..  code-block:: yaml

            - repo: https://github.com/Kintyre/ksconf
            rev: v0.11.8
            hooks:
                - id: ksconf-check
                - id: ksconf-sort
                exclude: logging\.conf
                - id: ksconf-xml-format
                  args: --disable-pre-commit-migration-check
            additional_dependencies: [lxml]

        But honestly, isn't it just easy to add ``-pre-commit`` to the repo?

        Remove this after Dec 2024 or v0.13.0
        """
        # New repo uses the following config:
        # entry: ksconf xml-format -q --disable-pre-commit-migration-check
        # If this flag has been used, assume we're running from the correct repo
        if args.disable_pre_commit_migration_check:
            return

        # See if pre-commit is my parent.  Assume this based on env variable.
        if os.environ.get("PRE_COMMIT", "") != "1":
            return

        from warnings import warn
        warn("You appear to be using the 'ksconf-xml-format' pre-commit hook from the ksconf repo. "
             "The ksconf pre-commit hooks have been moved to a new repo.  "
             "This configuration will stop working after v0.13.0 "
             "Please update '.pre-commit-config.yaml' to use the new "
             "repo: https://github.com/Kintyre/ksconf-pre-commit.git")

    def run(self, args):
        self.pre_commit_repo_migration_warning(args)
        formatter = SplunkSimpleXmlFormatter()
        # Should we read a list of conf files from STDIN?
        if len(args.xml) == 1 and args.xml[0] == "-":
            files = _stdin_iter()
        else:
            files = args.xml
        c = Counter()

        # Copy this locally, to avoid an even stranger exception later
        ParseError = etree.ParseError

        exit_code = EXIT_CODE_SUCCESS
        for fn in files:
            c["checked"] += 1
            if not os.path.isfile(fn):
                self.stderr.write(f"Skipping missing file:  {fn}\n")
                c["missing"] += 1
                continue
            try:
                if formatter.format_xml(fn, fn, args.indent):
                    self.stderr.write(f"Replaced file {fn} with formatted content\n")
                    c["changed"] += 1
                else:
                    if not args.quiet:
                        self.stderr.write(f"Already formatted {fn}\n")
                    c["no-action"] += 1
                self.stderr.flush()
            except ParseError as e:
                self.stderr.write(f"Error parsing file {fn}:  {e}\n")
                self.stderr.flush()
                c["error"] += 1
                exit_code = EXIT_CODE_BAD_CONF_FILE
            except Exception as e:  # pragma: no cover
                self.stderr.write(f"Unhandled top-level exception while parsing {fn}.  "
                                  f"Aborting.\n{e}\n")
                debug_traceback()
                c["error"] += 1
                exit_code = EXIT_CODE_INTERNAL_ERROR
                break

        if not exit_code and c["changed"] > 0:
            exit_code = EXIT_CODE_FORMAT_APPLIED

        if True:  # show stats or verbose
            self.stdout.write(f"Completed formatting {c['checked']} files.  "
                              f"rc={exit_code} Breakdown:\n"
                              f"   {c['changed']} files were formatted successfully.\n"
                              f"   {c['no-action']} files were already formatted.\n"
                              f"   {c['error']} files failed.\n")
        return exit_code
