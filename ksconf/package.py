from __future__ import absolute_import, unicode_literals

import os
import re
import shutil
import tarfile
import tempfile

from ksconf.conf.merge import merge_app_local, merge_conf_dicts
from ksconf.conf.parser import conf_attr_boolean, parse_conf, update_conf
from ksconf.consts import KSCONF_DEBUG
from ksconf.vc.git import git_cmd


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


class PackagingException(Exception):
    pass


class AppPackager(object):

    def __init__(self, src_path, app_name, output):
        self.src_path = src_path
        self.app_name = app_name
        self.build_dir = None
        self.app_dir = None
        self.output = output
        self._var_magic = None

    def cleanup(self):
        # Do we need  https://stackoverflow.com/a/21263493/315892  (Windows): -- See tests/cli_helper
        shutil.rmtree(self.build_dir)
        self.build_dir = None

    def expand_var(self, value):
        """ Expand a variable, if present

        :param str value:  String that main contain ``{{variable}}`` substitution.
        :return: Expanded value
        :rtype: str
        """
        return self._var_magic.expand(value)

    def expand_new_only(self, value):
        """ Expand a variable but return None if no substitution occurred

        :param str value:  String that main contain ``{{variable}}`` substitution.
        :return:  Expanded value if variables were expanded, else False
        :rtype: str
        """
        new_value = self._var_magic.expand(value)
        return new_value if new_value != value else False

    def combine(self, src, filters, layer_method="dir.d", allow_symlink=False):
        # VERY HACKY FOR NOW:
        args = ["combine", src, "--target", self.app_dir,
                "--layer-method", layer_method,
                # Stuff we shouldn't have to do with a proper interface:
                "--banner", "",
                "--quiet",
                "--disable-marker"]
        if allow_symlink:
            args.append("--follow-symlink")
        args += ["--{}={}".format(action, path) for (action, path) in filters]
        from ksconf.__main__ import cli

        # Passing in _unittest because that swaps sys.exit() for return
        rc = cli(args, _unittest=True)
        if rc != 0:
            raise PackagingException("Issue calling 'combine' internally during app build....")

    def blocklist(self, patterns):
        # XXX: Rewrite explicitly blocklist '.git' dir, because '*.git' wasn't working here. :=(

        # For now we just delete files out the build directory.  Not sophisticated, but it works
        # Do we need relwalker here?  relwalk
        from fnmatch import fnmatch
        for (root, dirs, files) in os.walk(self.build_dir, topdown=True):
            for fn in files:
                path = os.path.join(root, fn)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or fn == pattern:
                        self.output.write("Blocked file: {}  (pattern: {})\n".format(path, pattern))
                        os.unlink(path)
                        break
            for d in list(dirs):
                path = os.path.join(root, d)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or d == pattern:
                        self.output.write("Blocked dir:  {}  (pattern: {})\n".format(path, pattern))
                        dirs.remove(d)
                        shutil.rmtree(path)
                        break

    def merge_local(self):
        """
        Find everything in local, if it has a corresponding file in default, merge.
        """
        # XXX: No logging/reporting done here :-(
        merge_app_local(self.app_dir)
        # Cleanup anything remaining in local
        self.block_local(report=False)

    def block_local(self, report=True):
        local_dir = os.path.join(self.app_dir, "local")
        if os.path.isdir(local_dir):
            if report:
                self.output.write("Removing local directory.\n")
            shutil.rmtree(local_dir)
        local_meta = os.path.join(self.app_dir, "metadata", "local.meta")
        if os.path.isfile(local_meta):
            if report:
                self.output.write("Removing local.meta\n")
            os.unlink(local_meta)

    def update_app_conf(self, version=None, build=None):
        """ Update version and/or build in ``apps.conf`` """
        # type: (str, str) -> None
        app_settings = [
            ("launcher", "version", version),
            ("install", "build", build),
        ]
        appconf_file = find_conf_in_layers(self.app_dir, "app.conf") or \
            os.path.join(self.app_dir, "default", "app.conf")

        self.output.write("Updating app.conf file:  {}\n".format(appconf_file))
        with update_conf(appconf_file, make_missing=True) as conf:
            for (stanza, attr, value) in app_settings:
                new_value = self.expand_new_only(value)
                if value:
                    if stanza not in conf:
                        conf[stanza] = {}
                    if new_value:
                        self.output.write("\tUpdate app.conf:  [{}] {} = {}  (From {})\n"
                                          .format(stanza, attr, new_value, value))
                        value = new_value
                    else:
                        self.output.write("\tUpdate app.conf:  [{}] {} = {}\n"
                                          .format(stanza, attr, value))
                    conf[stanza][attr] = value

    def check(self):
        """ Run safety checks prior to building archive:

        1.  Set app name based on app.conf [package] id, if set.  Otherwise confirm that the package
            id and top-level folder names align.
        2.  Check for files or directories starting with ``.``, makes AppInspect very grumpy!
        """
        app_conf = get_merged_conf(self.app_dir, "app.conf")
        try:
            package_id = app_conf["package"]["id"]
            target_splunkbase = conf_attr_boolean(app_conf["package"]
                                                  .get("check_for_updates", "false"))
        except KeyError:
            self.output.write("Skipped folder and package id check due to missing app.conf entry\n")
            package_id = None

        if package_id:
            if not self.app_name or self.app_name == ".":
                self.output.write("Set app name from app.conf:  {}\n".format(self.app_name))
                self.app_name = package_id
            elif package_id != self.app_name:
                self.output.write("Top-level folder does not match the package id:  folder: {} "
                                  "package id: {}\n".format(self.app_name, package_id))
                if target_splunkbase:
                    raise PackagingException("Aborting build due to app name and package id "
                                             "discrepancy for public app")

        for root, dirs, files in os.walk(self.app_dir):
            for items, t in [(dirs, "directory"), (files, "file")]:
                for name in items:
                    if name[0] == ".":
                        self.output.write("Found hidden {}:  {}/{}\n".format(t, root, name))

    def make_archive(self, filename):
        """ Create a compressed tarball of the build directory.
        """
        # type: (str) -> str
        # if os.path.isfile(filename):
        #    raise ValueError("Destination file already exists:  {}".format(filename))

        # Python 3.2+, use context manager
        app_name = self.expand_var(self.app_name)
        if app_name != self.app_name:
            self.output.write("Expanding template {} to final app name: {}\n"
                              .format(self.app_name, app_name))

        new_filename = self.expand_new_only(filename)
        if new_filename:
            self.output.write("Creating archive:  {}  (Expanded from '{}'\n"
                              .format(new_filename, os.path.basename(filename)))
            filename = new_filename
        else:
            self.output.write("Creating archive:  {}\n".format(filename))

        spl = tarfile.open(filename, mode="w:gz")
        try:
            spl.add(self.app_dir, arcname=self.app_name)
        finally:
            spl.close()
        return filename

    def __enter__(self):
        self.build_dir = tempfile.mkdtemp("-ksconf-package-build")
        if self.app_name == "." or "{{" in self.app_name:
            # Use a placehold app name, specifically as "." causes build_dir == app_dir
            self.app_dir = os.path.join(self.build_dir, "app")
        else:
            self.app_dir = os.path.join(self.build_dir, self.app_name)
        self._var_magic = AppVarMagic(self.src_path, self.app_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class AppVarMagicException(KeyError):
    pass


class AppVarMagic(object):
    """ A lazy loading dict-like object to fetch things like app version and such on demand. """

    def __init__(self, src_dir, build_dir):
        self._cache = {}
        self.src_dir = src_dir
        self.build_dir = build_dir

    def expand(self, value):
        """ A simple Jinja2 like {{VAR}} substitution mechanism. """
        # type (str) -> str
        def replace(match_obj):
            var = match_obj.group(1)
            return self[var]
        if value:
            return re.sub(r"\{\{\s*([\w_]+)\s*\}\}", replace, value)
        return value

    def git_single_line(self, *args):
        out = git_cmd(args, cwd=self.src_dir)
        if out.returncode != 0:
            return "git-errorcode-{}".format(out.returncode)
        return out.stdout.strip()

    # START Variable fetching functions.  Be sure to add a docstring

    def get_version(self):
        """ Splunk app version fetched from app.conf """
        app_conf = get_merged_conf(self.build_dir, "app.conf")
        try:
            return app_conf["launcher"]["version"]
        except KeyError as e:
            raise AppVarMagicException(e)

    def get_build(self):
        """ Splunk app build fetched from app.conf """
        app_conf = get_merged_conf(self.build_dir, "app.conf")
        try:
            return app_conf["install"]["build"]
        except KeyError as e:
            raise AppVarMagicException(e)

    def get_app_id(self):
        """ Splunk app package id from app.conf """
        app_conf = get_merged_conf(self.build_dir, "app.conf")
        try:
            return app_conf["package"]["id"]
        except KeyError as e:
            raise AppVarMagicException(e)

    def get_git_tag(self):
        """ Git version tag using the ``git describe --tags`` command """
        tag = self.git_single_line("describe", "--tags", "--always", "--dirty")
        return re.sub(r'^(v|release|version)-?', "", tag)

    def get_git_last_rev(self):
        """ Git abbreviated rev of the last change of the app.  This may not be the same as HEAD. """
        return self.git_single_line("log", "-n1", "--pretty=format:%h", "--", ".")

    def get_git_head(self):
        """ Git HEAD rev abbreviated """
        return self.git_single_line("rev-parse", "--short", "HEAD")

    # END Variable fetching functions.

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
