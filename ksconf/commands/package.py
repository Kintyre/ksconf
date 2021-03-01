""" SUBCOMMAND:  ksconf package -f <SPL> <DIR>

Usage example:

    ksconf package -f myapp.tgz MyApp/


Build system example:

    ksconf package -f release/myapp-{{version}}.tgz \
            --block-local \
            --set-version=${git describe} \
            --set-build=${TRAVIS_BUILD_NUMBER:-0}


"""
from __future__ import absolute_import, unicode_literals

import argparse
import os

from ksconf.commands import KsconfCmd, dedent
from ksconf.consts import EXIT_CODE_SUCCESS, EXIT_CODE_BAD_ARGS
from ksconf.package import AppPackager


class PackageCmd(KsconfCmd):
    help = "Create a Splunk app .spl file from a source directory"
    description = dedent("""\
    Create a Splunk app or add on tarball (.spl) file from an app directory.

    ``ksconf package`` can do useful things like, exclude unwanted files, combine layers, set the
    application version and build number, drop or promote the ``local`` directory into ``default``.
    """)
    #format = "manual"
    maturity = "alpha"

    default_blocklist = [
        ".git*",
        "*.py[co]",
        "__pycache__",
        ".DS_Store"
    ]

    def register_args(self, parser):
        # type: (argparse.ArgumentParser) -> None

        def wb_type(action):
            def f(pattern):
                return action, pattern
            return f

        parser.add_argument("source", metavar="SOURCE",
                            help="Source directory for the Splunk app.")
        parser.add_argument("-f", "--file", metavar="SPL",
                            help="Name of splunk app file (tarball) to create.")

        parser.add_argument("--app-name",
                            help="Specify the top-level app folder name.  "
                                 "If this is not given, the app folder name is automatically "
                                 "extracted from the basename of SOURCE.")
        parser.add_argument("--blocklist", "-b",
                            action="append",
                            default=self.default_blocklist,
                            help="Pattern for files/directories to exclude.  "
                                 "Can be given multiple times.  You can load multiple exclusions "
                                 "from disk by using ``file://path`` which can be used "
                                 "with ``.gitignore`` for example.  (Default includes: {})"
                            .format(", ".join("``{}``".format(i) for i in self.default_blocklist)))

        # XXX: This should be smarter; stacked like we support for layers -- where order matters.
        parser.add_argument("--allowlist", "-w",
                            action="append", default=[],
                            help="Remove a pattern that was previously added to the blocklist.")

        player = parser.add_argument_group("Layer filtering",
            "If the app being packaged includes multiple layers, these arguments can be used to "
            "control which ones should be included in the final app file.  If no layer options "
            "are specified, then all layers will be included.")

        player.add_argument("--layer-method",
                            choices=["auto", "dir.d", "disable"],
                            default="auto",
                            help="Set the layer type used by SOURCE.  "
                                 "Additional description provided in in the ``combine`` command.")
        player.add_argument("-I", "--include", action="append", default=[], dest="layer_filter",
                            type=wb_type("include"), metavar="PATTERN",
                            help="Name or pattern of layers to include.")
        player.add_argument("-E", "--exclude", action="append", default=[], dest="layer_filter",
                            type=wb_type("exclude"), metavar="PATTERN",
                            help="Name or pattern of layers to exclude from the target.")

        parser.add_argument("--follow-symlink", "-l", action="store_true", default=False,
                            help="Follow symbolic links pointing to directories.  "
                                 "Symlinks to files are always followed.")

        # Set app version or extra app version.
        parser.add_argument("--set-version", metavar="VERSION",
                            help="Set application version.  By default the application version "
                                 "is read from default/app.conf")
        parser.add_argument("--set-build", metavar="BUILD",
                            help="Set application build number.")

        plocal = parser.add_mutually_exclusive_group()
        parser.set_defaults(local="merge")
        plocal.add_argument("--allow-local",
                            dest="local", action="store_const", const="preserve",
                            help="Allow the ``local`` folder to be kept as-is  "
                                 "WARNING: "
                                 "This goes against Splunk packaging practices, and will cause "
                                 "AppInspect to fail.  "
                                 "However, this option can be useful for private package transfers "
                                 "between servers, app backups, or other admin-like tasks.")
        plocal.add_argument("--block-local",
                            dest="local", action="store_const", const="block",
                            help="Block the ``local`` folder and ``local.meta`` from the package.")
        plocal.add_argument("--merge-local",
                            dest="local", action="store_const", const="merge",
                            help="Merge any files in ``local`` into the ``default`` folder during "
                                 "packaging.  This is the default behavior.")

        pbuild = parser.add_argument_group("Advanced Build Options",
                                           "The following options are for more advanced app "
                                           "building workflows.")
        pbuild.add_argument("--release-file",
                            help="Write the path of the newly generated archive file (SPL) after "
                                 "the archive is written.  "
                                 "This is useful in build scripts when the SPL contains variables "
                                 "so the final name may not be known ahead of time.")
        ''' # A better option here is ksconf.builder.  Let's avoid creating 2 mechanisms for the
            # same task (but technically this works)
        pbuild.add_argument("--hook-script", metavar="COMMAND",
                            action="append", default=[],
                            help="Run the given command or script.  "
                                 "This is run after all layer have been combined, and local "
                                 "directory handling, but before blocklist cleanup.  "
                                 "Therefore if this command produces any unwanted files they can "
                                 "be removed with a ``--blocklist`` entry. "
                                 "This can be used to install python packages, for example.")
        '''

    @staticmethod
    def load_blocklist(path):
        with open(path) as stream:
            for line in stream:
                line = line.rstrip()
                if line and not line.startswith("#"):
                    yield line

    def pre_run(self, args):
        if "local" in args.blocklist:
            self.stderr.write("Blocking 'local' is not supported.   "
                              "Most likely you want '--block-local' instead.\n")
            return EXIT_CODE_BAD_ARGS

        blocklist = []
        for pattern in args.blocklist:
            if pattern.startswith("file://"):
                blocklist_file = pattern[7:]
                expanded = list(self.load_blocklist(blocklist_file))
                self.stderr.write("Extended blocklist from {} with {:d} entries\n"
                                  .format(blocklist_file, len(expanded)))
                blocklist.extend(expanded)
            else:
                blocklist.append(pattern)
        args.blocklist = [pattern for pattern in blocklist if pattern not in args.allowlist]

    def run(self, args):
        ''' Create a Splunk app/add-on .spl file from a directory '''

        # Just call combine (writing to a temporary directory) and the tar it up.  At some point
        # we could do it all in memory, but for now this good enough.  And if we want the options of
        # interjecting a build script, then a build folder is necessary.

        app_name = args.app_name or os.path.basename(args.source)
        dest = args.file or "{}.tgz".format(app_name.lower().replace("-", "_"))
        builder = AppPackager(args.source, app_name, output=self.stderr)

        # XXX:  Make the combine step optional.  Either via detection (no .d folders/layers) OR manually opt-out for faster builds in simple scenarios
        with builder:
            builder.combine(args.source, args.layer_filter,
                            layer_method=args.layer_method,
                            allow_symlink=args.follow_symlink)
            # Handle local files
            if args.local == "merge":
                builder.merge_local()
            elif args.local == "block":
                builder.block_local()
            elif args.local == "preserve":
                pass
            else:   # pragma: no cover
                raise ValueError("Unknown value for 'local': {}".format(args.local))

            ''' # Disabling this for now.   Suggest using ksconf.builder.* instead
            for script in args.hook_script:
                builder.run_hook_script(script)
            '''

            if args.blocklist:
                self.stderr.write("Applying blocklist:  {!r}\n".format(args.blocklist))
                builder.blocklist(args.blocklist)

            if args.set_build or args.set_version:
                builder.update_app_conf(version=args.set_version,
                                        build=args.set_build)

            # os.system("ls -lR {}".format(builder.app_dir))

            dest = builder.var_magic.expand(dest)
            self.stderr.write("Creating archive:  {}\n".format(dest))
            builder.make_archive(dest)

            if args.release_file:
                # Should this be expanded to be an absolute path?
                with open(args.release_file, "w") as f:
                    f.write(dest)

        return EXIT_CODE_SUCCESS
