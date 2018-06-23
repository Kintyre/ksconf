#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
""" ksconf - Kintyre Splunk CONFig tool

Optionally supports argcomplete for commandline argument (tab) completion.

Install & register with:

     pip install argcomplete
     activate-global-python-argcomplete  (in ~/.bashrc)

"""

import argparse
import sys
import textwrap

import ksconf
import ksconf.util

from ksconf.consts import EXIT_CODE_INTERNAL_ERROR
from ksconf.commands import ConfFileProxy, ConfFileType
from ksconf.conf.parser import PARSECONF_MID_NC, PARSECONF_STRICT_NC, PARSECONF_STRICT, \
    PARSECONF_MID, PARSECONF_LOOSE

from ksconf.commands.check import do_check
from ksconf.commands.combine import do_combine
from ksconf.commands.diff import do_diff
from ksconf.commands.merge import do_merge
from ksconf.commands.minimize import do_minimize
from ksconf.commands.promote import do_promote
from ksconf.commands.sort import do_sort
from ksconf.commands.unarchive import do_unarchive



# For now, just effectively a copy of RawDescriptionHelpFormatter
class MyDescriptionHelpFormatter(argparse.HelpFormatter):
    def _fill_text(self, text, width, indent):
        # Looks like this one is ONLY used for the top-level description
        return ''.join([indent + line for line in text.splitlines(True)])

    def _split_lines(self, text, width):
        text = self._whitespace_matcher.sub(' ', text).strip()
        return textwrap.wrap(text, width)


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

    # Someday add *.meta (once more testing is done with those files
    conf_files_completer = FilesCompleter(allowednames=["*.conf"])

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
    parser.add_argument('--version', action='version', version='%(prog)s {}'.format(ksconf.version))
    parser.add_argument("--force-color", action="store_true", default=False,
                        help="Force TTY color mode on.  Useful if piping the output a color-aware "
                             "pager, like 'less -R'")

    # Logging settings -- not really necessary for simple things like 'diff', 'merge', and 'sort';
    # more useful for 'patch', very important for 'combine'

    subparsers = parser.add_subparsers()

    # SUBCOMMAND:  splconf check <CONF>
    sp_chck = subparsers.add_parser("check",
                                    help="Perform basic syntax and sanity checks on .conf files",
                                    description=
                                    "Provide basic syntax and sanity checking for Splunk's .conf "
                                    "files.  Use Splunk's builtin 'btool check' for a more robust "
                                    "validation of keys and values.\n\n"
                                    "Consider using this utility as part of a pre-commit hook.")
    sp_chck.set_defaults(funct=do_check)
    sp_chck.add_argument("conf", metavar="FILE", nargs="+",
                         help="One or more configuration files to check.  If the special value of "
                              "'-' is given, then the list of files to validate is read from "
                              "standard input"
                         ).completer = conf_files_completer
    sp_chck.add_argument("--quiet", "-q", default=False, action="store_true",
                         help="Reduce the volume of output.")
    ''' # Do we really need this?
    sp_chck.add_argument("--max-errors", metavar="INT", type=int, default=0,
                         help="Abort check if more than this many files fail validation.  Useful
                         for a pre-commit hook where any failure is unacceptable.")
    '''
    # Usage example:   find . -name '*.conf' | splconf check -  (Nice little pre-commit script)

    # SUBCOMMAND:  splconf combine --target=<DIR> <SRC1> [ <SRC-n> ]
    sp_comb = subparsers.add_parser("combine",
                                    help=
                                    "Merge configuration files from one or more source directories "
                                    "into a combined destination directory.  This allows for an "
                                    "arbitrary number of splunk's configuration layers within a "
                                    "single app.  Ad-hoc uses include merging the 'users' "
                                    "directory across several instances after a phased server "
                                    "migration.",
                                    description="""\
Merge .conf settings from multiple source directories into a combined target
directory.   Configuration files can be stored in a '/etc/*.d' like directory
structure and consolidated back into a single 'default' directory.

This command supports both one-time operations and recurring merge jobs.
For example, this command can be used to combine all users knowledge objects
(stored in 'etc/users') after a server migration, or to merge a single user's
settings after an their account has been renamed.  Recurring operations assume
some type of external scheduler is being used.  A best-effort is made to only
write to target files as needed.

The 'combine' command takes your logical layers of configs (upstream,
corporate, splunk admin fixes, and power user knowledge objects, ...)
expressed as individual folders and merges them all back into the single
'default' folder that Splunk reads from.  One way to keep the 'default'
folder up-to-date is using client-side git hooks.

No directory layout is mandatory, but but one simple approach is to model your
layers using a prioritized 'default.d' directory structure. (This idea is
borrowed from the Unix System V concept where many services natively read
their config files from '/etc/*.d' directories.)


THE PROBLEM:

In a typical enterprise deployment of Splunk, a single app can easily have
multiple logical sources of configuration:  (1) The upstream app developer,
(2) local developer app-developer  adds organization-specific customizations
or fixes, (3) splunk admin tweaks the inappropriate ''indexes.conf' settings,
and (4) custom knowledge objects added by your subject matter experts.
Ideally we'd like to version control these, but doing so is complicated
because normally you have to manage all 4 of these logical layers in one
'default' folder.  (Splunk requires that app settings be located either in
'default' or 'local'; and managing local files with version control leads to
merge conflicts; so effectively, all version controlled settings need to be in
'default', or risk merge conflicts.)  So when a new upstream version is
released, someone has to manually upgrade the app being careful to preserve
all custom configurations.  The solution provided by the 'combine'
functionality is that all of these logical sources can be stored separately in
their own physical directories allowing changes to be managed independently.
(This also allows for different layers to be mixed-and-matched by selectively
including which layers to combine.)  While this doesn't completely remove the
need for a human to review app upgrades, it does lower the overhead enough
that updates can be pulled in more frequently, thus reducing the divergence
potential.  (Merge frequently.)


NOTES:

The 'combine' command is similar to running the 'merge' subcommand recursively
against a set of directories.  One key difference is that this command will
gracefully handle non-conf files intelligently too.

EXAMPLE:

    Splunk_CiscoSecuritySuite/
    ├── README
    ├── default.d
    │   ├── 10-upstream
    │   │   ├── app.conf
    │   │   ├── data
    │   │   │   └── ui
    │   │   │       ├── nav
    │   │   │       │   └── default.xml
    │   │   │       └── views
    │   │   │           ├── authentication_metrics.xml
    │   │   │           ├── cisco_security_overview.xml
    │   │   │           ├── getting_started.xml
    │   │   │           ├── search_ip_profile.xml
    │   │   │           ├── upgrading.xml
    │   │   │           └── user_tracking.xml
    │   │   ├── eventtypes.conf
    │   │   ├── macros.conf
    │   │   ├── savedsearches.conf
    │   │   └── transforms.conf
    │   ├── 20-my-org
    │   │   └── savedsearches.conf
    │   ├── 50-splunk-admin
    │   │   ├── indexes.conf
    │   │   ├── macros.conf
    │   │   └── transforms.conf
    │   └── 70-firewall-admins
    │       ├── data
    │       │   └── ui
    │       │       └── views
    │       │           ├── attacks_noc_bigscreen.xml
    │       │           ├── device_health.xml
    │       │           └── user_tracking.xml
    │       └── eventtypes.conf

Commands:

    cd Splunk_CiscoSecuritySuite
    ksconf combine default.d/* --target=default

""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_comb.set_defaults(funct=do_combine)
    sp_comb.add_argument("source", nargs="+",
                         help="The source directory where configuration files will be merged from. "
                              "When multiple sources directories are provided, start with the most "
                              "general and end with the specific;  later sources will override "
                              "values from the earlier ones. Supports wildcards so a typical Unix "
                              "conf.d/##-NAME directory structure works well."
                         ).completer = DirectoriesCompleter()
    sp_comb.add_argument("--target", "-t",
                         help="Directory where the merged files will be stored.  Typically either "
                              "'default' or 'local'"
                         ).completer = DirectoriesCompleter()
    sp_comb.add_argument("--dry-run", "-D", default=False, action="store_true",
                         help="Enable dry-run mode.  Instead of writing to TARGET, show what "
                              "changes would be made to it in the form of a 'diff'. "
                              "If TARGET doesn't exist, then show the merged file.")
    sp_comb.add_argument("--banner", "-b",
                         default=" **** WARNING: This file is managed by 'ksconf combine', do not "
                                 "edit hand-edit this file! ****",
                         help="A warning banner telling discouraging editing of conf files.")

    # SUBCOMMAND:  splconf diff <CONF> <CONF>
    sp_diff = subparsers.add_parser("diff",
                                    help="Compares settings differences of two .conf files "
                                         "ignoring textual and sorting differences",
                                    description="""\
Compares the content differences of two .conf files

This command ignores textual differences (like order, spacing, and comments)
and focuses strictly on comparing stanzas, keys, and values.  Note that spaces
within any given value will be compared.  Multiline fields are compared in are
compared in a more traditional 'diff' output so that long savedsearches and
macros can be compared more easily.
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_diff.set_defaults(funct=do_diff)
    sp_diff.add_argument("conf1", metavar="CONF1", help="Left side of the comparison",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                         ).completer = conf_files_completer
    sp_diff.add_argument("conf2", metavar="CONF2", help="Right side of the comparison",
                         type=ConfFileType("r", "load", parse_profile=PARSECONF_MID_NC)
                         ).completer = conf_files_completer
    sp_diff.add_argument("-o", "--output", metavar="FILE",
                         type=argparse.FileType('w'), default=sys.stdout,
                         help="File where difference is stored.  Defaults to standard out.")
    sp_diff.add_argument("--comments", "-C",
                         action="store_true", default=False,
                         help="Enable comparison of comments.  (Unlikely to work consistently)")

    # SUBCOMMAND:  splconf promote --target=<CONF> <CONF>
    sp_prmt = subparsers.add_parser("promote",
                                    help="Promote .conf settings from one file into another either "
                                         "in batch mode (all changes) or interactively allowing "
                                         "the user to pick which stanzas and keys to integrate. "
                                         "Changes made via the UI (stored in the local folder) "
                                         "can be promoted (moved) to a version-controlled "
                                         "directory.",
                                    description="""\
Propagate .conf settings applied in one file to another.  Typically this is
used to take local changes made via the UI and push them into a default (or
default.d/) location.

NOTICE:  By default, changes are *MOVED*, not just copied.

Promote has two different modes:  batch and interactive.  In batch mode all
changes are applied automatically and the (now empty) source file is removed.
In interactive mode the user is prompted to pick which stanzas and keys to
integrate.  This can be used to push  changes made via the UI, which are
stored in a 'local' file, to the version-controlled 'default' file.  Note that
the normal operation moves changes from the SOURCE file to the TARGET,
updating both files in the process.  But it's also possible to preserve the
local file, if desired.

If either the source file or target file is modified while a promotion is
under progress, changes will be aborted.  And any custom selections you made
will be lost.  (This needs improvement.)
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_prmt.set_defaults(funct=do_promote, mode="ask")
    sp_prmt.add_argument("source", metavar="SOURCE",
                         type=ConfFileType("r+", "load", parse_profile=PARSECONF_STRICT_NC),
                         help="The source configuration file to pull changes from.  (Typically the "
                              "'local' conf file)"
                         ).completer = conf_files_completer
    sp_prmt.add_argument("target", metavar="TARGET",
                         type=ConfFileType("r+", "none", accept_dir=True,
                                           parse_profile=PARSECONF_STRICT),
                         help="Configuration file or directory to push the changes into. "
                              "(Typically the 'default' folder) "
                              "When a directory is given instead of a file then the same file name "
                              "is assumed for both SOURCE and TARGET"
                         ).completer = conf_files_completer
    sp_prg1 = sp_prmt.add_mutually_exclusive_group()
    sp_prg1.add_argument("--batch", "-b",
                         action="store_const",
                         dest="mode", const="batch",
                         help="Use batch mode where all configuration settings are automatically "
                              "promoted.  All changes are moved from the source to the target "
                              "file and the source file will be blanked or removed.")
    sp_prg1.add_argument("--interactive", "-i",
                         action="store_const",
                         dest="mode", const="interactive",
                         help="Enable interactive mode where the user will be prompted to approve "
                              "the promotion of specific stanzas and keys.  The user will be able "
                              "to apply, skip, or edit the changes being promoted.  (This "
                              "functionality was inspired by 'git add --patch').")
    sp_prmt.add_argument("--force", "-f",
                         action="store_true", default=False,
                         help="Disable safety checks.")
    sp_prmt.add_argument("--keep", "-k",
                         action="store_true", default=False,
                         help="Keep conf settings in the source file.  This means that changes "
                              "will be copied into the target file instead of moved there.")
    sp_prmt.add_argument("--keep-empty",
                         action="store_true", default=False,
                         help="Keep the source file, even if after the settings promotions the "
                              "file has no content.  By default, SOURCE will be removed if all "
                              "content has been moved into the TARGET location.  "
                              "Splunk will re-create any necessary local files on the fly.")

    """ Possible behaviors.... thinking through what CLI options make the most sense...

    Things we may want to control:

        Q: What mode of operation?
            1.)  Automatic (merge all)
            2.)  Interactive (user guided / sub-shell)
            3.)  Batch mode:  CLI driven based on a stanza or key using either a name or pattern to
                 select which content should be integrated.

        Q: What happens to the original?
            1.)  Updated
              a.)  Only remove source content that has been integrated into the target.
              b.)  Let the user pick
            2.)  Preserved  (Dry-run, or don't delete the original mode);  if output is stdout.
            3.)  Remove
              a.)  Only if all content was integrated.
              b.)  If user chose to discard entry.
              c.)  Always (--always-remove)
        Q: What to do with discarded content?
            1.)  Remove from the original (destructive)
            2.)  Place in a "discard" file.  (Allow the user to select the location of the file.)
            3.)  Automatically backup discards to a internal store, and/or log.  (More difficult to
                 recover, but content is always logged/recoverable with some effort.)


    Interactive approach:

        3 action options:
            Integrate/Accept: Move content from the source to the target  (e.g., local to default)
            Reject/Remove:    Discard content from the source; destructive (e.g., rm local setting)
            Skip/Keep:        Don't push to target or remove from source (no change)

    """

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

    # SUBCOMMAND:  splconf sort <CONF>
    sp_sort = subparsers.add_parser("sort",
                                    help="Sort a Splunk .conf file.  Sorted output can be echoed "
                                         "or files can be sorted inplace.",
                                    description="""\
Sort a Splunk .conf file.  Sort has two modes:  (1) by default, the sorted
config file will be echoed to the screen.  (2) the config files are updated
inplace when the '-i' option is used.

Conf files that are manually managed that you don't ever want sorted can be
'blacklisted' by placing the string 'KSCONF-NO-SORT' in a comment at the top
of the .conf file.

To recursively sort all files:

    find . -name '*.conf' | xargs ksconf sort -i
""",
                                    formatter_class=MyDescriptionHelpFormatter)
    sp_sort.set_defaults(funct=do_sort)

    sp_sort.add_argument("conf", metavar="FILE", nargs="+",
                         type=argparse.FileType('r'), default=[sys.stdin],
                         help="Input file to sort, or standard input."
                         ).completer = conf_files_completer
    group = sp_sort.add_mutually_exclusive_group()
    group.add_argument("--target", "-t", metavar="FILE",
                       type=argparse.FileType('w'), default=sys.stdout,
                       help="File to write results to.  Defaults to standard output."
                       ).completer = conf_files_completer
    group.add_argument("--inplace", "-i",
                       action="store_true", default=False,
                       help="Replace the input file with a sorted version.  Warning this a "
                            "potentially destructive operation that may move/remove comments.")
    sp_sog1 = sp_sort.add_argument_group("In-place update arguments")
    sp_sog1.add_argument("-F", "--force", action="store_true",
                         help="Force file sorting for all files, even for files containing the "
                              "special 'KSCONF-NO-SORT' marker.")
    sp_sog1.add_argument("-q", "--quiet", action="store_true",
                         help="Reduce the output.  Reports only updated or invalid files.  "
                              "This is useful for pre-commit hooks, for example.")
    sp_sort.add_argument("-n", "--newlines", metavar="LINES", type=int, default=1,
                         help="Lines between stanzas.")

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

    try:
        return_code = args.funct(args)
    except Exception, e:  # pragma: no cover
        sys.stderr.write("Unhandled top-level exception.  {0}\n".format(e))
        raise
        return_code = EXIT_CODE_INTERNAL_ERROR

    if _unittest:
        return return_code or 0
    else:  # pragma: no cover
        sys.exit(return_code or 0)


if __name__ == '__main__':  # pragma: no cover
    cli()
