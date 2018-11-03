#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
""" ksconf - Kintyre Splunk CONFig tool

Optionally supports argcomplete for commandline argument (tab) completion.

Install & register with:

     pip install argcomplete
     activate-global-python-argcomplete  (in ~/.bashrc)

"""

from __future__ import absolute_import
from __future__ import unicode_literals

import argparse
import sys

import ksconf
import ksconf.util
from ksconf.commands import KsconfCmd, MyDescriptionHelpFormatter, get_entrypoints
from ksconf.util.completers import autocomplete
from ksconf.consts import EXIT_CODE_INTERNAL_ERROR

###################################################################################################
## CLI definition


# ------------------------------------------ wrap to 80 chars ----------------v
_cli_description = """Ksconf: Kintyre Splunk CONFig tool

This utility handles a number of common Splunk app maintenance tasks in a small
and easy to deploy package.  Specifically, this tools deals with many of the
nuances with storing Splunk apps in git, and pointing live Splunk apps to a git
repository.  Merging changes from the live system's (local) folder to the
version controlled (default) folder, and dealing with more than one layer of
"default" (which splunk can't handle natively) are all supported tasks.
"""
# ------------------------------------------ wrap to 80 chars ----------------^


def cli(argv=None, _unittest=False):
    parser = argparse.ArgumentParser(fromfile_prefix_chars="@",
                                     formatter_class=MyDescriptionHelpFormatter,
                                     description=_cli_description,
                                     prog="ksconf")

    subparsers = parser.add_subparsers()

    version_info = []

    from random import choice
    # XXX:  Check terminal size before picking a signature
    version_info.append(choice(ksconf.__ascii_sigs__))
    version_info.append("%(prog)s {}  (Build {})".format(ksconf.__version__, ksconf.__build__))
    version_info.append("Python: {}  ({})".format(sys.version.split()[0], sys.executable))
    if ksconf.__vcs_info__:
        version_info.append(ksconf.__vcs_info__)
    version_info.append("Written by {}.".format(ksconf.__author__))
    version_info.append("Copyright {}.".format(ksconf.__copyright__))
    version_info.append("Licensed under {}".format(ksconf.__license__))

    version_info.append("\nCommands:")
    # Add entry-point subcommands
    # XXX:  Eventually lazy load subcommands to save resources.   (Low priority)
    for (name, entry) in get_entrypoints("ksconf_cmd").items():
    # sys.stderr.write("Loading {} from entry point:  {!r}\n".format(name, entry))
        cmd_cls = entry.load()
        distro = entry.dist or "Unknown"
        version_info.append("    {:15} ({})".format(name, distro))

        if not issubclass(cmd_cls, KsconfCmd):
            raise RuntimeError("Entry point {!r} not derived from KsconfCmd.".format(entry))

        cmd = cmd_cls(entry.name)
        cmd.add_parser(subparsers)


    # Common settings
    '''
    ### DEPRECATE THESE
    parser.add_argument("-S", "--duplicate-stanza", default=DUP_EXCEPTION, metavar="MODE",
                        choices=[DUP_MERGE, DUP_OVERWRITE, DUP_EXCEPTION],
                        help="Set duplicate stanza handling mode.  If [stanza] exists more than "
                             "once in a single .conf file:  Mode 'overwrite' will keep the last "
                             "stanza found.  Mode 'merge' will merge keys from across all stanzas, "
                             "keeping the the value form the latest key.  Mode 'exception' "
                             "(default) will abort if duplicate stanzas are found.")
    parser.add_argument("-K", "--duplicate-key", default=DUP_EXCEPTION, metavar="MODE",
                        choices=[DUP_EXCEPTION, DUP_OVERWRITE],
                        help="Set duplicate key handling mode.  A duplicate key is a condition "
                             "that occurs when the same key (key=value) is set within the same "
                             "stanza.  Mode of 'overwrite' silently ignore duplicate keys, "
                             "keeping the latest.  Mode 'exception', the default, aborts if "
                             "duplicate keys are found.")
    '''
    parser.add_argument('--version', action='version', version="\n".join(version_info))
    parser.add_argument("--force-color", action="store_true", default=False,
                        help="Force TTY color mode on.  Useful if piping the output a color-aware "
                             "pager, like 'less -R'")

    # Logging settings -- not really necessary for simple things like 'diff', 'merge', and 'sort';
    # more useful for 'patch', very important for 'combine'


    autocomplete(parser)
    args = parser.parse_args(argv)

    ksconf.util.terminal.FORCE_TTY_COLOR = args.force_color

    # This becomes a thing in Python 3.6
    if not hasattr(args, "funct") or args.funct is None:
        sys.stderr.write(parser.format_usage())
        sys.exit(1)

    try:
        return_code = args.funct(args)
    except Exception as e:  # pragma: no cover
        # Todo:  Make a CLI arg or ENV var to enable stacktrace for debugging
        sys.stderr.write("Unhandled top-level exception.  {0}\n".format(e))
        ksconf.util.debug_traceback()
        return_code = EXIT_CODE_INTERNAL_ERROR

    if _unittest:
        return return_code or 0
    else:  # pragma: no cover
        sys.exit(return_code or 0)


if __name__ == '__main__':  # pragma: no cover
    cli()
