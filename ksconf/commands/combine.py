# -*- coding: utf-8 -*-
""" SUBCOMMAND:  ``combine --target=<DIR> <SRC1> [ <SRC-n> ]``

Usage example:

.. code-block:: sh

    cd MY_APP
    ksconf combine default.d/* --target=default

"""
from __future__ import absolute_import, unicode_literals

import os
from io import open

from ksconf.combine import LayerCombiner, LayerCombinerException
from ksconf.commands import KsconfCmd, dedent
from ksconf.consts import (EXIT_CODE_BAD_ARGS, EXIT_CODE_COMBINE_MARKER_MISSING,
                           EXIT_CODE_MISSING_ARG, EXIT_CODE_NO_SUCH_FILE)
from ksconf.filter import create_filtered_list
from ksconf.util.completers import DirectoriesCompleter
from ksconf.util.file import expand_glob_list, relwalk, splglob_simple

CONTROLLED_DIR_MARKER = ".ksconf_controlled"


class LayerCombinerExceptionCode(LayerCombinerException):
    def __init__(self, msg, return_code=None):
        super().__init__(msg)
        self.return_code = return_code


class RepeatableCombiner(LayerCombiner):
    """
    Re-runable combiner class.  Beyond the reusable layer combining functionality,
    this class enables the use of a marker file for added safety.  Removed files
    will cleanup.
    """

    def __init__(self, *args,
                 disable_marker: bool = False,
                 disable_cleanup: bool = False,
                 keep_existing: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_extra_files: set = None
        self.disable_marker = disable_marker
        self.disable_cleanup = disable_cleanup
        self.keep_existing = keep_existing

    def prepare_target_dir(self, target):
        """
        Handle marker file and ensure that target directory gets created safely.
        """
        marker_file = os.path.join(target, CONTROLLED_DIR_MARKER)
        if os.path.isdir(target):
            if not self.disable_marker and not os.path.isfile(marker_file):
                self.stderr.write("Target directory already exists, but it appears to have been "
                                  "created by some other means.  Marker file missing.\n")
                raise LayerCombinerExceptionCode("Target directory exists without marker file",
                                                 EXIT_CODE_COMBINE_MARKER_MISSING)

        elif self.dry_run:
            self.stderr.write("Skipping creating destination directory {target} (dry-run)\n")
        else:
            try:
                os.mkdir(target)
            except OSError as e:
                self.stderr.write(f"Unable to create destination directory {target}.  {e}\n")
                raise LayerCombinerExceptionCode(f"Unable to create destination directory {target}",
                                                 EXIT_CODE_NO_SUCH_FILE)
            self.stderr.write(f"Created destination directory {target}\n")
            if not self.disable_marker:
                with open(marker_file, "w") as f:
                    f.write("This directory is managed by KSCONF.  Don't touch\n")

    def pre_combine_inventory(self, target, src_files):
        """
        Find a set of files that exist in the target folder, but in NO source folder (for cleanup)
        """
        config = self.config

        self.stderr.write(f"Layers detected:  {self.layer_names_all}\n")
        if self.layer_names_all != self.layer_names_used:
            self.stderr.write(f"Layers after filter: {self.layer_names_used}\n")

        # Convert src_files to a set to speed up
        src_files = set(src_files)
        self.target_extra_files = set()
        for (root, dirs, files) in relwalk(target, followlinks=config.follow_symlink):
            for fn in files:
                tgt_file = os.path.join(root, fn)
                if tgt_file not in src_files:
                    if fn == CONTROLLED_DIR_MARKER or config.block_files.search(fn):
                        continue  # pragma: no cover (peephole optimization)
                    self.target_extra_files.add(tgt_file)
        return src_files

    def post_combine(self, target):
        """
        Handle cleanup of extra files
        """
        target_extra_files = self.target_extra_files
        if target_extra_files:
            if self.disable_cleanup:
                self.stderr.write("Cleanup operations disabled by user.\n")
            else:
                self.stderr.write("Found extra files not part of source tree(s):  "
                                  f"{len(target_extra_files)} files.\n")

            keep_existing = create_filtered_list("splunk", default=False)
            # splglob_simple:  Either full paths, or simple file-only match
            keep_existing.feedall(self.keep_existing, filter=splglob_simple)
            for dest_fn in target_extra_files:
                if keep_existing.match_path(dest_fn):
                    self.stderr.write(f"Keep existing file {dest_fn}\n")
                elif self.disable_cleanup:
                    self.stderr.write(f"Skip cleanup of unwanted file {dest_fn}\n")
                else:
                    self.stderr.write(f"Remove unwanted file {dest_fn}\n")
                    os.unlink(os.path.join(target, dest_fn))


class CombineCmd(KsconfCmd):
    help = dedent("""\
    Combine configuration files across multiple source directories into a single
    destination directory.  This allows for an arbitrary number of Splunk
    configuration layers to coexist within a single app.  Useful in both ongoing
    merge and one-time ad-hoc use.
    """)
    description = dedent("""\
    Merge .conf settings from multiple source directories into a combined target
    directory.  Configuration files can be stored in a ``/etc/*.d`` like directory
    structure and consolidated back into a single 'default' directory.

    This command supports both one-time operations and recurring merge jobs.  For
    example, this command can be used to combine all users' knowledge objects (stored
    in 'etc/users') after a server migration, or to merge a single user's settings
    after their account has been renamed.  Recurring operations assume some type
    of external scheduler is being used.  A best-effort is made to only write to
    target files as needed.

    The 'combine' command takes your logical layers of configs (upstream, corporate,
    Splunk admin fixes, and power user knowledge objects, ...) expressed as
    individual folders and merges them all back into the single ``default`` folder
    that Splunk reads from.  One way to keep the 'default' folder up-to-date is
    using client-side git hooks.

    No directory layout is mandatory, but taking advantages of the native-support
    for 'dir.d' layout works well for many uses cases.  This idea is borrowed from
    the Unix System V concept where many services natively read their config files
    from ``/etc/*.d`` directories.

    Version notes:  dir.d was added in ksconf 0.8.  Starting in 1.0 the default will
    switch to 'dir.d', so if you need the old behavior be sure to update your scripts.
    """)
    format = "manual"
    maturity = "beta"

    def register_args(self, parser):

        def wb_type(action):
            def f(pattern):
                return action, pattern
            return f

        parser.add_argument("source", nargs="+", help=dedent("""
            The source directory where configuration files will be merged from.
            When multiple source directories are provided, start with the most general and end
            with the specific; later sources will override values from the earlier ones.
            Supports wildcards so a typical Unix ``conf.d/##-NAME`` directory structure works well.""")
                            ).completer = DirectoriesCompleter()
        parser.add_argument("--target", "-t", help=dedent("""
            Directory where the merged files will be stored.
            Typically either 'default' or 'local'""")
                            ).completer = DirectoriesCompleter()
        parser.add_argument("-m", "--layer-method",
                            choices=["auto", "dir.d", "disable"],
                            default="auto",
                            help="""
            Set the layer type used by SOURCE.

            Use ``dir.d`` if you have directories like ``MyApp/default.d/##-layer-name``, or use
            ``disable`` to manage layers explicitly and avoid any accidental layer detection.
            By default, ``auto`` mode will enable transparent switching between 'dir.d' and 'disable'
            (legacy) behavior.
            """)

        parser.add_argument("-q", "--quiet", action="store_true",
                            help="Make output a bit less noisy.  This may change in the future...")

        parser.add_argument("-I", "--include", action="append", default=[], dest="layer_filter",
                            type=wb_type("include"), metavar="PATTERN",
                            help="Name or pattern of layers to include.")
        parser.add_argument("-E", "--exclude", action="append", default=[], dest="layer_filter",
                            type=wb_type("exclude"), metavar="PATTERN",
                            help="Name or pattern of layers to exclude from the target.")
        parser.add_argument("--dry-run", "-D", default=False, action="store_true", help=dedent("""
            Enable dry-run mode.
            Instead of writing to TARGET, preview changes as a 'diff'.
            If TARGET doesn't exist, then show the merged file."""))
        parser.add_argument("--follow-symlink", "-l", action="store_true", default=False,
                            help="Follow symbolic links pointing to directories.  "
                                 "Symlinks to files are always followed.")
        parser.add_argument("--banner", "-b",
                            default=" **** WARNING: This file is managed by 'ksconf combine', do "
                                    "not edit hand-edit this file! ****",
                            help="A banner or warning comment added to the top of the TARGET file. "
                                 "Used to discourage Splunk admins from editing an auto-generated "
                                 "file.")
        parser.add_argument("-K", "--keep-existing", action="append", default=[],
                            help="Existing file(s) to preserve in the TARGET folder.  "
                            "This argument may be used multiple times.")
        parser.add_argument("--disable-marker", action="store_true", default=False, help=dedent(f"""
            Prevents the creation of or checking for the ``{CONTROLLED_DIR_MARKER}`` marker file safety check.
            This file is typically used indicate that the destination folder is managed by ksconf.
            This option should be reserved for well-controlled batch processing scenarios.
            """))
        parser.add_argument("--disable-cleanup", action="store_true", default=False,
                            help="Disable all file removal operations.  Skip the cleanup phase "
                            "that typically removes files in TARGET that no longer exist in SOURCE")

    def run(self, args):
        combiner = RepeatableCombiner(follow_symlink=args.follow_symlink, banner=args.banner, dry_run=args.dry_run, quiet=args.quiet,
                                      keep_existing=args.keep_existing, disable_cleanup=args.disable_cleanup, disable_marker=args.disable_marker)

        # For now, just copy all settings from 'args' to class instance... needs work
        combiner.stdout = self.stdout
        combiner.stderr = self.stderr

        for (action, pattern) in args.layer_filter:
            combiner.add_layer_filter(action, pattern)

        # Expand any globs in the CLI to individual directories
        args.source = list(expand_glob_list(args.source, do_sort=True))

        if args.layer_method == "auto":
            self.stderr.write(
                "Warning:  Automatically guessing an appropriate directory layer detection.  "
                "Consider using '--layer-method' to avoid this warning.\n")
            if len(args.source) == 1:
                layer_method = "dir.d"
            else:
                layer_method = "disable"
        else:
            layer_method = args.layer_method

        if layer_method == "dir.d":
            self.stderr.write("Using automatic '*.d' directory layer detection.\n")
            if len(args.source) > 1:
                # XXX: Lift this restriction, if possible.  Seems like this *should* be doable. idk
                self.stderr.write("ERROR:  Only one source directory is allowed when running the "
                                  "'dir.d' layer mode.\n")
                return EXIT_CODE_BAD_ARGS

            combiner.set_layer_root(args.source[0])
            layer_root = combiner.layer_root
            for (dir, layers) in layer_root._mount_points.items():
                self.stderr.write(f"Found layer parent folder:  {dir}  "
                                  f"with layers {', '.join(layers)}\n")
        else:
            self.stderr.write("Automatic layer detection is disabled.\n")
            for src in args.source:
                self.stderr.write(f"Reading conf files from directory {src}\n")
            combiner.set_source_dirs(args.source)

        if args.target is None:
            self.stderr.write("Must provide the '--target' directory.\n")
            return EXIT_CODE_MISSING_ARG

        self.stderr.write(f"Combining files into directory {args.target}\n")

        try:
            combiner.combine(args.target)
        except LayerCombinerExceptionCode as e:
            return e.return_code
