# -*- coding: utf-8 -*-
""" SUBCOMMAND:  combine --target=<DIR> <SRC1> [ <SRC-n> ]

Usage example:

    cd MY_APP
    ksconf combine default.d/* --target=default

"""
from __future__ import absolute_import, unicode_literals

import os
import re
from collections import defaultdict

from ksconf.commands import ConfFileProxy
from ksconf.commands import KsconfCmd, dedent
from ksconf.conf.delta import show_text_diff
from ksconf.conf.merge import merge_conf_files
from ksconf.conf.parser import PARSECONF_MID, PARSECONF_STRICT
from ksconf.consts import EXIT_CODE_MISSING_ARG, EXIT_CODE_COMBINE_MARKER_MISSING, SMART_NOCHANGE
from ksconf.util.compare import file_compare
from ksconf.util.completers import DirectoriesCompleter
from ksconf.util.file import _expand_glob_list, relwalk, _is_binary_file, smart_copy

CONTROLLED_DIR_MARKER = ".ksconf_controlled"


class CombineCmd(KsconfCmd):
    help = dedent("""\
    Combine configuration files across multiple source directories into a single
    destination directory.  This allows for an arbitrary number of splunk
    configuration layers to coexist within a single app.  Useful in both ongoing
    merge and one-time ad-hoc use.
    """)
    description = dedent("""\
    Merge .conf settings from multiple source directories into a combined target
    directory.   Configuration files can be stored in a ``/etc/*.d`` like directory
    structure and consolidated back into a single 'default' directory.

    This command supports both one-time operations and recurring merge jobs.  For
    example, this command can be used to combine all users knowledge objects (stored
    in 'etc/users') after a server migration, or to merge a single user's settings
    after an their account has been renamed.  Recurring operations assume some type
    of external scheduler is being used.  A best-effort is made to only write to
    target files as needed.

    The 'combine' command takes your logical layers of configs (upstream, corporate,
    splunk admin fixes, and power user knowledge objects, ...) expressed as
    individual folders and merges them all back into the single ``default`` folder
    that Splunk reads from.  One way to keep the 'default' folder up-to-date is
    using client-side git hooks.

    No directory layout is mandatory, but but one simple approach is to model your
    layers using a prioritized 'default.d' directory structure. (This idea is
    borrowed from the Unix System V concept where many services natively read their
    config files from ``/etc/*.d`` directories.)
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):
        parser.add_argument("source", nargs="+", help=dedent("""
            The source directory where configuration files will be merged from.
            When multiple sources directories are provided, start with the most general and end
            with the specific; later sources will override values from the earlier ones.
            Supports wildcards so a typical Unix ``conf.d/##-NAME`` directory structure works well."""
                            )).completer = DirectoriesCompleter()
        parser.add_argument("--target", "-t", help=dedent("""
            Directory where the merged files will be stored.
            Typically either 'default' or 'local'"""
                            )).completer = DirectoriesCompleter()
        parser.add_argument("--dry-run", "-D", default=False, action="store_true", help=dedent("""
            Enable dry-run mode.
            Instead of writing to TARGET, preview changes as a 'diff'.
            If TARGET doesn't exist, then show the merged file."""))
        parser.add_argument("--banner", "-b",
                            default=" **** WARNING: This file is managed by 'ksconf combine', do "
                                    "not edit hand-edit this file! ****",
                            help="A banner or warning comment added to the top of the TARGET file. "
                                 "Used to discourage Splunk admins from editing an auto-generated "
                                 "file.")

    def run(self, args):
        # Ignores case sensitivity.  If you're on Windows, name your files right.
        conf_file_re = re.compile("([a-z]+\.conf|(default|local)\.meta)$")

        if args.target is None:
            self.stderr.write("Must provide the '--target' directory.\n")
            return EXIT_CODE_MISSING_ARG

        self.stderr.write("Combining conf files into directory {}\n".format(args.target))
        args.source = list(_expand_glob_list(args.source))
        for src in args.source:
            self.stderr.write("Reading conf files from directory {}\n".format(src))

        marker_file = os.path.join(args.target, CONTROLLED_DIR_MARKER)
        if os.path.isdir(args.target):
            if not os.path.isfile(os.path.join(args.target, CONTROLLED_DIR_MARKER)):
                self.stderr.write("Target directory already exists, but it appears to have been"
                                  "created by some other means.  Marker file missing.\n")
                return EXIT_CODE_COMBINE_MARKER_MISSING
        elif args.dry_run:
            self.stderr.write(
                "Skipping creating destination directory {0} (dry-run)\n".format(args.target))
        else:
            self.stderr.write("Creating destination directory {0}\n".format(args.target))
            os.mkdir(args.target)
            open(marker_file, "w").write("This directory is managed by KSCONF.  Don't touch\n")

        # Build a common tree of all src files.
        src_file_index = defaultdict(list)
        for src_root in args.source:
            for (root, dirs, files) in relwalk(src_root):
                for fn in files:
                    # Todo: Add blacklist CLI support:  defaults to consider: *sw[po], .git*, .bak, .~
                    if fn.endswith(".swp") or fn.endswith("*.bak"):
                        continue  # pragma: no cover  (peephole optimization)
                    src_file = os.path.join(root, fn)
                    src_path = os.path.join(src_root, root, fn)
                    src_file_index[src_file].append(src_path)

        # Find a set of files that exist in the target folder, but in NO source folder (for cleanup)
        target_extra_files = set()
        for (root, dirs, files) in relwalk(args.target):
            for fn in files:
                tgt_file = os.path.join(root, fn)
                if tgt_file not in src_file_index:
                    # Todo:  Add support for additional blacklist wildcards (using fnmatch)
                    if fn == CONTROLLED_DIR_MARKER or fn.endswith(".bak"):
                        continue  # pragma: no cover (peephole optimization)
                    target_extra_files.add(tgt_file)

        for (dest_fn, src_files) in sorted(src_file_index.items()):
            # Source file must be in sort order (10-x is lower prio and therefore replaced by 90-z)
            src_files = sorted(src_files)
            dest_path = os.path.join(args.target, dest_fn)

            # Make missing destination folder, if missing
            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir) and not args.dry_run:
                os.makedirs(dest_dir)

            # Handle conf files and non-conf files separately
            if not conf_file_re.search(dest_fn):
                # self.stderr.write("Considering {0:50}  NON-CONF Copy from source:  {1!r}\n".format(dest_fn, src_files[-1]))
                # Always use the last file in the list (since last directory always wins)
                src_file = src_files[-1]
                if args.dry_run:
                    if os.path.isfile(dest_path):
                        if file_compare(src_file, dest_path):
                            smart_rc = SMART_NOCHANGE
                        else:
                            if (_is_binary_file(src_file) or _is_binary_file(dest_path)):
                                # Binary files.  Can't compare...
                                smart_rc = "DRY-RUN (NO-DIFF=BIN)"
                            else:
                                show_text_diff(self.stdout, dest_path, src_file)
                                smart_rc = "DRY-RUN (DIFF)"
                    else:
                        smart_rc = "DRY-RUN (NEW)"
                else:
                    smart_rc = smart_copy(src_file, dest_path)
                if smart_rc != SMART_NOCHANGE:
                    self.stderr.write(
                        "Copy <{0}>   {1:50}  from {2}\n".format(smart_rc, dest_path, src_file))
            else:
                try:
                    # Handle merging conf files
                    dest = ConfFileProxy(os.path.join(args.target, dest_fn), "r+",
                                         parse_profile=PARSECONF_MID)
                    srcs = [ConfFileProxy(sf, "r", parse_profile=PARSECONF_STRICT) for sf in src_files]
                    # self.stderr.write("Considering {0:50}  CONF MERGE from source:  {1!r}\n".format(dest_fn, src_files[0]))
                    smart_rc = merge_conf_files(dest, srcs, dry_run=args.dry_run,
                                                banner_comment=args.banner)
                    if smart_rc != SMART_NOCHANGE:
                        self.stderr.write(
                            "Merge <{0}>   {1:50}  from {2!r}\n".format(smart_rc, dest_path,
                                                                        src_files))
                finally:
                    # Protect against any dangling open files:  (ResourceWarning: unclosed file)
                    dest.close()
                    for src in srcs:
                        src.close()

        if True and target_extra_files:  # Todo: Allow for cleanup to be disabled via CLI
            self.stderr.write("Cleaning up extra files not part of source tree(s):  {0} files.\n".
                format(len(target_extra_files)))
            for dest_fn in target_extra_files:
                self.stderr.write("Remove unwanted file {0}\n".format(dest_fn))
                os.unlink(os.path.join(args.target, dest_fn))
