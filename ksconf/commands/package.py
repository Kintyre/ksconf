""" SUBCOMMAND:  ``ksconf package -f <SPL> <DIR>``

Usage example:

.. code-block:: sh

   ksconf package -f myapp.tgz MyApp/


Build system example:

.. code-block:: sh

    ksconf package -f release/myapp-{{version}}.tgz \\
            --block-local \\
            --set-version={{git_tag}} \\
            --set-build=${TRAVIS_BUILD_NUMBER:-0}


"""
from __future__ import absolute_import, unicode_literals

import argparse
import os

from ksconf.commands import KsconfCmd, dedent
from ksconf.consts import EXIT_CODE_BAD_ARGS, EXIT_CODE_SUCCESS
from ksconf.package import AppPackager


class PackageCmd(KsconfCmd):
    help = "Create a Splunk app .spl file from a source directory"
    description = dedent("""\
    Create a Splunk app or add on tarball (``.spl``) file from an app directory.

    ``ksconf package`` can do useful things like, exclude unwanted files, combine layers, set the
    application version and build number, drop or promote the ``local`` directory into ``default``.

    Note that some arguments, like the ``FILE`` support special values that can be automatically
    evaluated at runtime.  For example the placeholders ``{{version}}`` or ``{{git_tag}}`` can be
    expanded into the output tarball filename.
    """)
    # format = "manual"
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
                            help="Name of splunk app file (tarball) to create.  "
                            "Placeholder variables in ``{{var}}`` syntax can be used here.")

        parser.add_argument("--app-name",
                            help="Specify the top-level app folder name.  "
                                 "If this is not given, the app folder name is automatically "
                                 "extracted from the basename of SOURCE.  "
                                 "Placeholder variables, such as ``{{app_id}}`` can be used here.")
        parser.add_argument("--blocklist", "-b",
                            action="append",
                            default=self.default_blocklist,
                            help="Pattern for files/directories to exclude.  "
                                 "Can be given multiple times.  You can load multiple exclusions "
                                 "from disk by using ``file://path`` which can be used "
                                 "with ``.gitignore`` for example.  (Default includes: {})"
                            .format(", ".join("``{}``".format(i) for i in self.default_blocklist)))

        # XXX: This should be smarter; stacked like we support for layers -- where order matters.
        parser.add_argument("--allowlist", "-a",
                            action="append", default=[],
                            help="Remove a pattern that was previously added to the blocklist.")

        player = parser.add_argument_group(
            "Layer filtering",
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
                                 "is read from default/app.conf.  Placeholder variables such as "
                                 "``{{git_tag}}`` can be used here.")
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
        # we should do it all in memory, but for now this good enough.  For more sophisticated
        # builds use a temp build directory.  This is what ksconf's BuildManager does.

        app_name = args.app_name
        app_name_source = "set via commandline"
        if not app_name:
            app_name = os.path.basename(args.source)
            app_name_source = "taken from source directory"
            '''
            if os.path.basename(args.source) == ".":
                app_name = os.path.basename(os.getcwd())
                app_name_source = "extracted from working directory"
            else:
                app_name = os.path.basename(args.source)
                app_name_source = "extracted from source directory"
        '''
        self.stdout.write("Packaging {}   (App name {})\n".format(app_name, app_name_source))
        packager = AppPackager(args.source, app_name, output=self.stderr)

        # XXX:  Make the combine step optional.  Either via detection (no .d folders/layers) OR manually opt-out
        #       for faster packaging in simple scenarios (this may not matter once this is done in memory)
        with packager:
            packager.combine(args.source, args.layer_filter,
                             layer_method=args.layer_method,
                             allow_symlink=args.follow_symlink)
            # Handle local files
            if args.local == "merge":
                packager.merge_local()
            elif args.local == "block":
                packager.block_local()
            elif args.local == "preserve":
                pass
            else:   # pragma: no cover
                raise ValueError("Unknown value for 'local': {}".format(args.local))

            if args.blocklist:
                self.stderr.write("Applying blocklist:  {!r}\n".format(args.blocklist))
                packager.blocklist(args.blocklist)

            if args.set_build or args.set_version:
                packager.update_app_conf(
                    version=args.set_version,
                    build=args.set_build)

            packager.check()
            # os.system("ls -lR {}".format(packager.app_dir))

            dest = args.file or "{}-{{{{version}}}}.tgz".format(packager.app_name.lower().replace("-", "_"))
            archive_path = packager.make_archive(dest)
            self.stderr.write("Archive created:  file={} size={:.2f}Kb\n".format(
                os.path.basename(archive_path), os.stat(archive_path).st_size / 1024.0))

            if args.release_file:
                # Should this be expanded to be an absolute path?
                with open(args.release_file, "w") as f:
                    f.write(archive_path)

        return EXIT_CODE_SUCCESS
