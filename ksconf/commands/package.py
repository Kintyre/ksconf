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
import shutil
import tempfile
import os
import re
import shutil
import tarfile


from ksconf.commands import KsconfCmd, dedent, ConfFileType
from ksconf.conf.parser import parse_conf, update_conf
from ksconf.conf.merge import merge_conf_dicts
from ksconf.vc.git import git_cmd
from ksconf.util.file import relwalk
from ksconf.consts import EXIT_CODE_SUCCESS, EXIT_CODE_BAD_ARGS, KSCONF_DEBUG


def find_conf_in_layers(app_dir, conf, *layers):
    if not layers:
        layers = ("local", "default")
    for layer in layers:
        conf_file = os.path.join(app_dir, layer, conf)
        if os.path.isfile(conf_file):
            return conf_file

def get_merged_conf(app_dir, conf, *layers):
    if not layers:
        # Last layer wins
        layers = ("default", "local")
    files = [os.path.join(app_dir, layer, conf) for layer in layers]
    confs = [parse_conf(path) for path in files if os.path.isfile(path)]
    return merge_conf_dicts(*confs)


class AppVarMagicException(KeyError):
    pass


class AppVarMagic(object):
    """ A lazy loading dict-like object to fetch things like app version and such on demand. """

    def __init__(self, src_dir, build_dir):
        self._cache = {}
        self.src_dir = src_dir
        self.build_dir = build_dir

    def expand(self, value):
        #  A very simple Jinja2 like {{VAR}} replacement mechanism.  Someday we may use Jinja2,
        # but for now we just need var substitution.
        def replace(match_obj):
            var = match_obj.group(1)
            return self[var]
        return re.sub(r"\{\{\s*([\w_]+)\s*\}\}", replace, value)

    def git_singline(self, *args):
        out = git_cmd(args, cwd=self.src_dir)
        if out.returncode != 0:
            return "git-errorcode-{}".format(out.returncode)
        return out.stdout.strip()

    ## START Variable fetching functions.  Be sure to add a docstring

    def get_version(self):
        """ Splunk app version fetched from app.conf """
        app_conf = get_merged_conf(self.build_dir, "app.conf")
        try:
            return app_conf["launcher"]["version"]
        except KeyError:
            raise AppVarMagicException()

    def get_build(self):
        """ Splunk app build fetched from app.conf """
        app_conf = get_merged_conf(self.build_dir, "app.conf")
        try:
            return app_conf["launcher"]["version"]
        except KeyError:
            raise AppVarMagicException()

    def get_git_tag(self):
        """ Git version tag using the 'git describe --tags' command """
        tag = self.git_singline("describe", "--tags", "--always", "--dirty")
        return re.sub(r'^(v|release|version)-', "", tag)

    def get_git_last_rev(self):
        """ Git abbreviated rev of the last change of the app.  This may not be the same as HEAD. """
        return self.git_singline("log", "-n1", "--pretty=format:%h", "--", ".")

    def get_git_head(self):
        """ Git HEAD rev abbreviated """
        return self.git_singline("rev-parse", "--short", "HEAD")

    ## END Variable fetching functions.

    def list_vars(self):
        """ Return a list of (variable, description) available in this class. """
        for name in dir(self):
           if name.startswith("get_"):
                var = name[4:]
                doc = getattr(self, name).__doc__.strip()
                yield (var, doc)

    def __getitem__(self, item):
        get_funct_name = "get_" + item
        if hasattr(self, get_funct_name):
            try:
                funct = getattr(self, get_funct_name)
                return funct()
            except AppVarMagicException as e:
                if KSCONF_DEBUG in os.environ:
                    raise e
                return "VAR-{}-ERROR".format(item)
        else:
            raise KeyError(item)


class AppPackageBuilder(object):

    def __init__(self, src_path, app_name, output):
        self.src_path = src_path
        self.app_name = app_name
        self.build_dir = None
        self.app_dir = None
        self.output = output
        self.var_magic = None

    def cleanup(self):
        # Do we need  https://stackoverflow.com/a/21263493/315892  (Windows): -- See tests/cli_helper
        shutil.rmtree(self.build_dir)

    def combine(self, src, filters, layer_method="dir.d", allow_symlink=False):
        # VERY HACKY FOR NOW:
        args = [ "combine", src, "--target", self.app_dir,
                 "--layer-method", layer_method,
                 # Stuff we shouldn't have to do with a proper interface:
                 "--banner", "",
                 "--disable-marker" ]
        if allow_symlink:
            args.append("--follow-symlink")
        args += [ "--{}={}".format(action, path) for (action, path) in filters ]
        from ksconf.__main__ import cli

        # Passing in _unittest because that swaps sys.exit() for return
        rc = cli(args, _unittest=True)
        if rc != 0:
            raise ValueError("Issue calling 'combine' internally during app build....")

    def blocklist(self, patterns):
        # XXX:  Rewrite -- Had to hack the layers to explicitly blocklist '.git' dir, because '*.git' wasn't working here. :=(

        # For now we just delete files out the build directory.  Not sophisticated, but it works
        # Do we need relwalker here?  relwalk
        from fnmatch import fnmatch
        for (root, dirs, files) in os.walk(self.build_dir, topdown=True):
            for fn in files:
                path = os.path.join(root, fn)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or fn == pattern:
                        self.output.write("Blacklisted file: {}  (pattern: {})\n".format(path, pattern))
                        os.unlink(path)
                        break
            for d in list(dirs):
                path = os.path.join(root, d)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or d == pattern:
                        self.output.write("Blacklisted dir:  {}  (pattern: {})\n".format(path, pattern))
                        dirs.remove(d)
                        shutil.rmtree(path)
                        break

    def merge_local(self):
        raise NotImplementedError
        # XXX: Recursive merge:   local --> default.
        # XXX: Merge local.meta -> default.meta

    def block_local(self):
        local_dir = os.path.join(self.app_dir, "local")
        if os.path.isdir(local_dir):
            self.output.write("Removing local directory.\n")
            shutil.rmtree(local_dir)
        local_meta = os.path.join(self.app_dir, "metadata", "local.meta")
        if os.path.isfile(local_meta):
            self.output.write("Removing local.meta\n")
            os.unlink(local_meta)

    def update_app_conf(self, version=None, build=None):
        app_settings = [
            ("launcher", "version", version),
            ("install", "build", build),
        ]
        appconf_file = find_conf_in_layers(self.app_dir, "app.conf") or \
            os.path.join(self.app_dir, "default", "app.conf")

        self.output.write("Updating app.conf file:  {}\n".format(appconf_file))
        with update_conf(appconf_file, make_missing=True) as conf:
            for (stanza, attr, value) in app_settings:
                if value:
                    if stanza not in conf:
                        conf[stanza] = {}
                    self.output.write("\tUpdate app.conf:  [{}] {} = {}\n".format(stanza, attr, value))
                    conf[stanza][attr] = value

    def run_hook_script(self, script):
        # XXX: Add environmental vars and such to make available to the script
        from subprocess import Popen
        if os.path.isfile(script):
            self.output.write("Running external hook script: {}\n".format(script))
            proc = Popen([script], cwd=self.app_dir, shell=False)
        else:
            self.output.write("Running external hook shell:  {}\n".format(script))
            proc = Popen(script, cwd=self.app_dir, shell=True)
        proc.wait()
        if proc.returncode !=0:
            raise Exception("Hook script returned non-0.  Aborting")

    def make_archive(self, filename):
        #if os.path.isfile(filename):
        #    raise ValueError("Destination file already exists:  {}".format(filename))

        # Doh:  version 3.2: Added support for the context management protocol.  (need to wait to use it)
        spl = tarfile.open(filename, mode="w:gz")
        spl.add(self.app_dir, arcname=self.app_name)
        spl.close()

    def __enter__(self):
        self.build_dir = tempfile.mkdtemp("-ksconf-package-build")
        self.app_dir = os.path.join(self.build_dir, self.app_name)
        self.var_magic = AppVarMagic(self.src_path, self.app_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


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
                            help="Allow the local folder to be kept.  "
                                 "WARNING: "
                                 "This goes against Splunk packaging practices, and will cause "
                                 "AppInspect to fail.  "
                                 "However, this option can be useful for private package transfers "
                                 "between servers or possibly for app backups.")
        plocal.add_argument("--block-local",
                            dest="local", action="store_const", const="block",
                            help="Block the local folder and local.meta from the resulting SPL.")
        plocal.add_argument("--merge-local",
                            dest="local", action="store_const", const="merge",
                            help="Merge any files in local into the default folder when build the "
                                 "archive.  This is the default behavior.")

        pbuild = parser.add_argument_group("Advanced Build Options",
                                           "The following options are for more advanced app "
                                           "building workflows.")
        pbuild.add_argument("--release-file",
                            help="Write the path of the newly generated archive file (SPL) after "
                                 "the archive is written.  "
                                 "This is useful in build scripts when the SPL contains variables "
                                 "so the final name may not be known ahead of time.")
        pbuild.add_argument("--hook-script", metavar="COMMAND",
                            action="append", default=[],
                            help="Run the given command or script.  "
                                 "This is run after all layer have been combined, and local "
                                 "directory handling, but before blocklist cleanup.  "
                                 "Therefore if this command produces any unwanted files they can "
                                 "be removed with a ``--blocklist`` entry. "
                                 "This can be used to install python packages, for example.")

    @staticmethod
    def load_blocklist(path):
        with open(path) as stream:
            for line in stream:
                line = line.rstrip()
                if line and not line.startswith("#"):
                    yield line

    def pre_run(self, args):
        if "local" in args.blocklist:
            self.stderr.write("Blacklisting 'local' is not supported.   "
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
        builder = AppPackageBuilder(args.source, app_name, output=self.stderr)
        with builder:
            builder.combine(args.source, args.layer_filter, allow_symlink=args.follow_symlink)
            # Handle local files
            if args.local == "merge":
                builder.merge_local()
            elif args.local == "block":
                builder.block_local()
            elif args.local == "preserve":
                pass
            else:   # pragma: no cover
                raise ValueError("Unknown value for 'local': {}".format(args.local))

            for script in args.hook_script:
                builder.run_hook_script(script)

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
                open(args.release_file, "w").write(dest)

        return EXIT_CODE_SUCCESS
