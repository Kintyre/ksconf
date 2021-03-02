from __future__ import absolute_import, unicode_literals

import os
import re
import shutil
import tarfile
import tempfile

from ksconf.conf.merge import merge_app_local, merge_conf_dicts
from ksconf.conf.parser import update_conf, parse_conf
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


class AppPackager(object):

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
                 "--quiet",
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

    '''
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
        if proc.returncode != 0:
            raise Exception("Hook script returned non-0.  Aborting")
    '''

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

    def git_single_line(self, *args):
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
        tag = self.git_single_line("describe", "--tags", "--always", "--dirty")
        return re.sub(r'^(v|release|version)-', "", tag)

    def get_git_last_rev(self):
        """ Git abbreviated rev of the last change of the app.  This may not be the same as HEAD. """
        return self.git_single_line("log", "-n1", "--pretty=format:%h", "--", ".")

    def get_git_head(self):
        """ Git HEAD rev abbreviated """
        return self.git_single_line("rev-parse", "--short", "HEAD")

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
