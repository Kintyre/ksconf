""" SUBCOMMAND:  ksconf package -f <SPL> <DIR>

Usage example:

    ksconf package -f myapp.tgz MyApp/

"""
from __future__ import absolute_import, unicode_literals

import argparse
import shutil
import tempfile
import os
import re
import tarfile


from ksconf.commands import KsconfCmd, dedent, ConfFileType
from ksconf.consts import EXIT_CODE_SUCCESS



class AppNameMagic(object):
    """ A lazy loading dict-like object to fetch things like app version and such on demand. """

    def __init__(self, app_dir):
        self._cache = {}
        self.path = app_dir

    def get_version(self):
        ###
        return ""

    def __getitem__(self, item):
        if item in self._cache:
            value = self._cache[item]
        else:
            get_funct_name = "get_" + item
            if hasattr(self, get_funct_name):
                get_funct = getattr(self, get_funct_name)
                value = self._cache[item] = get_funct()
        return value



class AppPackageBuilder(object):

    def __init__(self, app_name):
        self.app_name = app_name
        self.build_dir = None
        self.app_dir = None

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

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class PackageCmd(KsconfCmd):
    help = "Create a Splunk app .spl file from an application directory"
    description = dedent("""\
    Create a Splunk app or add on tarball (.spl) file file from an app directory.

    This function can do several useful things like, exclude unwanted files, combine layers, set the
    application version and build number, drop or merge the local directory into default.
    """)
    format = "manual"
    maturity = "alpha"

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

        parser.add_argument("--blacklist", "-b",
                            action="append",
                            default=["*.py[co]", "__pycache__", ".DS_Store", ".git*"],
                            help="Pattern for files/directories to exclude.")


        parser.add_argument("-I", "--include", action="append", default=[], dest="layer_filter",
                            type=wb_type("include"), metavar="PATTERN",
                            help="Name or pattern of layers to include.")
        parser.add_argument("-E", "--exclude", action="append", default=[], dest="layer_filter",
                            type=wb_type("exclude"), metavar="PATTERN",
                            help="Name or pattern of layers to exclude from the target.")

        parser.add_argument("--follow-symlink", "-l", action="store_true", default=False,
                            help="Follow symbolic links pointing to directories.  "
                                 "Symlinks to files are always followed.")
        # Set app version or extra app version.
        '''
        parser.add_argument("--set-version",
                            help="Set application version.  By default the application version "
                                 "is read from default/app.conf")
        parser.add_argument("--set-build",
                            help="Set application build number.")
        '''


        # Local handling
        '''
        plocal = parser.add_mutually_exclusive_group()
        plocal.add_argument("--allow-local",
                            dest="local", action="store_const", const="preserve",
                            help="Allow the local folder to be kept.  "
                                 "This goes against Splunk packaging practices, and will cause "
                                 "AppInspect to fail.  "
                                 "However, this could be useful for local packaging deployment.")
        plocal.add_argument("--block-local",
                            dest="local", action="store_const", const="block",
                            help="Block the local folder from inclusion in the resulting SPL.")
        plocal.add_argument("--merge-local",
                            dest="local", action="store_const", const="merge", default="merge",
                            help="Merge any files in local into the default folder when build the "
                                 "archive.  This is the default behavior.")
        '''

    def run(self, args):
        ''' Create a Splunk app/add-on .spl file from a directory '''

        # Just call combine (writing to a temporary directory) and the tar it up.  At some point
        # we could do it all in memory, but for now this good enough.  And if we want the options of
        # interjecting a build script, then a build folder is necessary.

        app_name = os.path.basename(args.source)
        dest = args.file or "{}.tar.gz".format(app_name.lower().replace("-", "_"))
        builder = AppPackageBuilder(app_name)
        with builder:
            builder.combine(args.source, args.layer_filter, allow_symlink=args.follow_symlink)
            # os.system("ls -lR {}".format(builder.app_dir))
            self.stderr.write("Creating archive:  {}".format(dest))
            builder.make_archive(dest)


        #if rc == EXIT_CODE_DIFF_EQUAL:
        #    self.stderr.write("Files are the same.\n")
        #elif rc == EXIT_CODE_DIFF_NO_COMMON:
        #    self.stderr.write("No common stanzas between files.\n")
        return EXIT_CODE_SUCCESS
