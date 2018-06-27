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

from ksconf.consts import EXIT_CODE_INTERNAL_ERROR
from ksconf.commands import ConfFileProxy, ConfFileType
from ksconf.conf.parser import PARSECONF_MID_NC, PARSECONF_STRICT_NC, PARSECONF_STRICT, \
    PARSECONF_MID, PARSECONF_LOOSE
from ksconf.util.completers import conf_files_completer

from ksconf.commands import KsconfCmd, MyDescriptionHelpFormatter, get_entrypoints

from ksconf.commands.merge import do_merge
from ksconf.commands.minimize import do_minimize
from ksconf.commands.unarchive import do_unarchive





# Optional argcomplete library for CLI (BASH-based) tab completion
try:
    from argcomplete import autocomplete
    from argcomplete.completers import FilesCompleter, DirectoriesCompleter
except ImportError:  # pragma: no cover
    def _argcomplete_noop(*args, **kwargs): del args, kwargs


    autocomplete = _argcomplete_noop
    # noinspection PyPep8Naming
    FilesCompleter = DirectoriesCompleter = _argcomplete_noop


####################################################################################################
## CLI definition


# ------------------------------------------ wrap to 80 chars ----------------v
_cli_description = """Kintyre Splunk CONFig tool.

This utility handles a number of common Splunk app maintenance tasks in a small
and easy to relocate package.  Specifically, this tools deals with many of the
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

    version_info = '%(prog)s {}\n'.format(ksconf.version)

    version_info += "\nCommands:"
    # Add entry-point subcommands
    for (name, entry) in get_entrypoints("ksconf_cmd").items():
        #sys.stderr.write("Loading {} from entry point:  {!r}\n".format(name, entry))
        cmd_cls = entry.load()
        distro = entry.dist or "Unknown"
        version_info += "\n    {:15} ({})".format(name, distro)

        if not issubclass(cmd_cls, KsconfCmd):
            raise RuntimeError("Entry point {!r} targets a class not derived from KsconfCmd.".format(entry))

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
    parser.add_argument('--version', action='version', version=version_info)
    parser.add_argument("--force-color", action="store_true", default=False,
                        help="Force TTY color mode on.  Useful if piping the output a color-aware "
                             "pager, like 'less -R'")

    # Logging settings -- not really necessary for simple things like 'diff', 'merge', and 'sort';
    # more useful for 'patch', very important for 'combine'



    # SUBCOMMAND:  splconf merge --target=<CONF> <CONF> [ <CONF-n> ... ]
    sp_merg = subparsers.add_parser("merge",
                                    help="Merge two or more .conf files",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_merg.set_defaults(funct=do_merge)
    sp_merg.add_argument("conf", metavar="FILE", nargs="+",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID),
                         help="The source configuration file to pull changes from."
                         ).completer = conf_files_completer
    sp_merg.add_argument("--target", "-t", metavar="FILE",
                         type=ConfFileType("r+", "none", parse_profile=PARSECONF_STRICT),
                         default=ConfFileProxy("<stdout>", "w", sys.stdout),
                         help="Save the merged configuration files to this target file.  If not "
                              "given, the default is to write the merged conf to standard output."
                         ).completer = conf_files_completer
    sp_merg.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing to TARGET, show what "
                              "changes would be made to it in the form of a 'diff'. "
                              "If TARGET doesn't exist, then show the merged file.")
    sp_merg.add_argument("--banner", "-b", default="",
                         help="A banner or warning comment to add to the TARGET file.  Often used "
                              "to warn Splunk admins from editing a auto-generated file.")

    # SUBCOMMAND:  splconf minimize --target=<CONF> <CONF> [ <CONF-n> ... ]
    # Example workflow:
    #   1. cp default/props.conf local/props.conf
    #   2. vi local/props.conf (edit JUST the lines you want to change)
    #   3. splconf minimize --target=local/props.conf default/props.conf
    #  (You could take this a step further by appending "$SPLUNK_HOME/system/default/props.conf"
    # and removing any SHOULD_LINEMERGE = true entries (for example)
    sp_minz = subparsers.add_parser("minimize",
                                    help="Minimize the target file by removing entries duplicated "
                                         "in the default conf(s) provided.  ",
                                    description="""\
Minimize a conf file by removing the default settings

Reduce local conf file to only your indented changes without manually tracking
which entires you've edited.  Minimizing local conf files makes your local
customizations easier to read and often results in cleaner add-on upgrades.

A typical scenario & why does this matter:
To customizing a Splunk app or add-on, start by copying the conf file from
default to local and then applying your changes to the local file.  That's
good.  But stopping here may complicated future upgrades, because the local
file doesn't contain *just* your settings, it contains all the default
settings too.  Fixes published by the app creator may be masked by your local
settings.  A better approach is to reduce the local conf file leaving only the
stanzas and settings that you indented to change.  This make your conf files
easier to read and makes upgrades easier, but it's tedious to do by hand.

For special cases, the '--explode-default' mode reduces duplication between
entries normal stanzas and global/default entries.  If 'disabled = 0' is a
global default, it's technically safe to remove that setting from individual
stanzas.  But sometimes it's preferable to be explicit, and this behavior may
be too heavy-handed for general use so it's off by default.  Use this mode if
your conf file that's been fully-expanded.  (i.e., conf entries downloaded via
REST, or the output of "btool list").  This isn't perfect, since many apps
push their settings into the global namespace, but it can help.


Example usage:

    cd Splunk_TA_nix
    cp default/inputs.conf local/inputs.conf

    # Edit 'disabled' and 'interval' settings in-place
    vi local/inputs.conf

    # Remove all the extra (unmodified) bits
    ksconf minimize --target=local/inputs.conf default/inputs.conf

""",
                                    formatter_class=MyDescriptionHelpFormatter)
    '''Make sure this works before advertising (same file as target and source????)
    # Note:  Use the 'merge' command to "undo"
    ksconf merge --target=local/inputs.conf default/inputs local/inputs.conf
    '''
    sp_minz.set_defaults(funct=do_minimize)
    sp_minz.add_argument("conf", metavar="FILE", nargs="+",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_LOOSE),
                         help="The default configuration file(s) used to determine what base "
                              "settings are unnecessary to keep in the target file."
                         ).completer = conf_files_completer
    sp_minz.add_argument("--target", "-t", metavar="FILE",
                         type=ConfFileType("r+", "load", parse_profile=PARSECONF_STRICT),
                         help="This is the local file that you with to remove the duplicate "
                              "settings from.  By default, this file will be read and the updated "
                              "with a minimized version."
                         ).completer = conf_files_completer
    sp_mzg1 = sp_minz.add_mutually_exclusive_group()
    sp_mzg1.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing the minimized value to "
                              "TARGET, show a 'diff' of what would be removed.")
    sp_mzg1.add_argument("--output",
                         type=ConfFileType("w", "none", parse_profile=PARSECONF_STRICT),
                         default=None,
                         help="When this option is used, the new minimized file will be saved to "
                              "this file instead of updating TARGET.  This can be use to preview "
                              "changes or helpful in other workflows."
                         ).completer = conf_files_completer
    sp_minz.add_argument("--explode-default", "-E", default=False, action="store_true",
                         help="Along with minimizing the same stanza across multiple config files, "
                              "also take into consideration the [default] or global stanza values. "
                              "This can often be used to trim out cruft in savedsearches.conf by "
                              "pointing to etc/system/default/savedsearches.conf, for example.")
    sp_minz.add_argument("-k", "--preserve-key",
                         action="append", default=[],
                         help="Specify a key that should be allowed to be a duplication but should "
                              "be preserved within the minimized output.  For example the it's"
                              "often desirable keep the 'disabled' settings in the local file, "
                              "even if it's enabled by default.")


    # SUBCOMMAND:  splconf upgrade tarball
    sp_unar = subparsers.add_parser("unarchive",
                                    help="Install or overwrite an existing app in a git-friendly "
                                         "way.  If the app already exist, steps will be taken to "
                                         "upgrade it safely.",
                                    formatter_class=MyDescriptionHelpFormatter)
    # Q:  Should this also work for fresh installs?
    sp_unar.set_defaults(funct=do_unarchive)
    sp_unar.add_argument("tarball", metavar="SPL",
                         help="The path to the archive to install."
                         ).completer = FilesCompleter(allowednames=("*.tgz", "*.tar.gz", "*.spl",
                                                                    "*.zip"))
    sp_unar.add_argument("--dest", metavar="DIR", default=".",
                         help="Set the destination path where the archive will be extracted.  "
                              "By default the current directory is used, but sane values include "
                              "etc/apps, etc/deployment-apps, and so on.  This could also be a "
                              "git repository working tree where splunk apps are stored."
                         ).completer = DirectoriesCompleter()
    sp_unar.add_argument("--app-name", metavar="NAME", default=None,
                         help="The app name to use when expanding the archive.  By default, the "
                              "app name is taken from the archive as the top-level path included "
                              "in the archive (by convention)  Expanding archives that contain "
                              "multiple (ITSI) or nested apps (NIX, ES) is not supported.")
    sp_unar.add_argument("--default-dir", default="default", metavar="DIR",
                         help="Name of the directory where the default contents will be stored.  "
                              "This is a useful feature for apps that use a dynamic default "
                              "directory that's created by the 'combine' mode."
                         ).completer = DirectoriesCompleter()
    sp_unar.add_argument("--exclude", "-e", action="append", default=[],
                         help="Add a file pattern to exclude.  Splunk's psudo-glob "
                              "patterns are supported here.  '*' for any non-directory match, "
                              "'...' for ANY (including directories), and '?' for a single "
                              "character.")
    sp_unar.add_argument("--keep", "-k", action="append", default=[],
                         help="Add a pattern of file to preserve during an upgrade.")
    sp_unar.add_argument("--allow-local", default=False, action="store_true",
                         help="Allow local/ and local.meta files to be extracted from the archive. "
                              "This is a Splunk packaging violation and therefore by default these "
                              "files are excluded.")
    sp_unar.add_argument("--git-sanity-check",
                         choices=["off", "changed", "untracked", "ignored"],
                         default="untracked",
                         help="By default a 'git status' is run on the destination folder to see "
                              "if the working tree or index has modifications before the unarchive "
                              "process starts.  "
                              "The choices go from least restrictive to most thorough: "
                              "Use 'off' to prevent any 'git status' safely checks. "
                              "Use 'changed' to abort only upon local modifications to files "
                              "tracked by git. "
                              "Use 'untracked' (by default) to look for changed and untracked "
                              "files before considering the tree clean. "
                              "Use 'ignored' to enable the most intense safety check which will "
                              "abort if local changes, untracked, or ignored files are found. "
                              "(These checks are automatically disabled if the app is not in a git "
                              "working tree, or git is not present.)")
    sp_unar.add_argument("--git-mode", default="stage",
                         choices=["nochange", "stage", "commit"],
                         help="Set the desired level of git integration.  "
                              "The default mode is 'stage', where new, updated, or removed files "
                              "are automatically handled for you.  If 'commit' mode is selected, "
                              "then files are committed with an  auto-generated commit message.  "
                              "To prevent any 'git add' or 'git rm' commands from being run, pick "
                              "the 'nochange' mode. "
                              "  Notes:  "
                              "(1) The git mode is irrelevant if the app is not in a git working "
                              "tree.  "
                              "(2) If a git commit is incorrect, simply roll it back with "
                              "'git reset' or fix it with a 'git commit --amend' before the "
                              "changes are pushed anywhere else.  (That's why you're using git in "
                              "the first place, right?)")
    sp_unar.add_argument("--no-edit",
                         action="store_true", default=False,
                         help="Tell git to skip opening your editor.  By default you will be "
                              "prompted to review/edit the commit message.  (Git Tip:  Delete the "
                              "content of the message to abort the commit.)")
    sp_unar.add_argument("--git-commit-args", "-G", default=[], action="append")

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
        sys.stderr.write("Unhandled top-level exception.  {0}\n".format(e))
        raise
        return_code = EXIT_CODE_INTERNAL_ERROR

    if _unittest:
        return return_code or 0
    else:  # pragma: no cover
        sys.exit(return_code or 0)


if __name__ == '__main__':  # pragma: no cover
    cli()
