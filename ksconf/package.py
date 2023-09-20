from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import os
import re
import shutil
import tarfile
import tempfile
from functools import wraps
from os import fspath
from pathlib import Path
from typing import TextIO, Union

from ksconf.app.manifest import AppManifest
from ksconf.combine import LayerCombiner
from ksconf.conf.merge import merge_app_local, merge_conf_dicts
from ksconf.conf.parser import conf_attr_boolean, parse_conf, update_conf
from ksconf.consts import is_debug
from ksconf.hook import plugin_manager
from ksconf.util import decorator_with_opt_kwargs
from ksconf.util.file import atomic_writer
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


def normalize_directory_mtime(path):
    """ Walk a tree and update the directory modification times to match the
    newest time of the children.  This results in a more predictable behavior
    over multiple executions.
    """
    for (root, dirs, files) in os.walk(path, topdown=False):
        nodes = dirs + files
        if not nodes:
            # Empty directories are somewhat unlikely.  We'll see
            continue
        mtime = max(os.stat(os.path.join(root, n)).st_mtime for n in nodes)
        os.utime(root, (mtime, mtime))


class PackagingException(Exception):
    pass


class AppPackager:

    def __init__(self, src_path, app_name: str, output: TextIO,
                 template_variables: dict = None,
                 predictable_mtime: bool = True):
        self.src_path = fspath(src_path)
        self.app_name = app_name
        self.build_dir = None
        self.app_dir = None
        self.output = output
        self._var_magic = None
        self._mutable = None
        self._frozen_by = str
        self.template_variables = template_variables
        self.predictable_mtime = predictable_mtime

    @decorator_with_opt_kwargs
    def require_active_context(funct, mutable=True):
        """ Decorator to mark member functions that cannot be used until the
        context manager has been activated.
        """
        @wraps(funct)
        def wrapper(self: AppPackager, *args, **kwargs):
            assert self.build_dir, "Context manager not yet active"
            if mutable:
                # Ensure make_archive() and make_manifest() are called last
                assert self._mutable, "App content already frozen. " \
                    f"Must call {funct.__name__}() before {self._frozen_by}()"
            return funct(self, *args, **kwargs)
        return wrapper

    def cleanup(self):
        # Do we need  https://stackoverflow.com/a/21263493/315892  (Windows): -- See tests/cli_helper
        shutil.rmtree(self.build_dir)
        self.build_dir = None
        self.app_dir = None
        self._mutable = None

    def expand_var(self, value: str) -> str:
        """ Expand a variable, if present

        :param str value:  String that main contain ``{{variable}}`` substitution.
        :return: Expanded value
        :rtype: str
        """
        return self._var_magic.expand(value)

    def expand_new_only(self, value: str) -> Union[str, None]:
        """ Expand a variable but return False if no substitution occurred

        :param str value:  String that may contain ``{{variable}}`` substitution.
        :return:  Expanded value if variables were expanded, else False
        :rtype: str
        """
        new_value = self._var_magic.expand(value)
        return new_value if new_value != value else False

    @require_active_context
    def combine(self, src, filters, layer_method="dir.d", allow_symlink=False):
        combiner = LayerCombiner(follow_symlink=allow_symlink, quiet=True)
        if self.template_variables:
            combiner.context.template_variables = self.template_variables
        if layer_method == "dir.d":
            combiner.set_layer_root(src)
        elif layer_method == "disable":
            combiner.set_source_dirs([src])
        else:
            raise NotImplementedError(f"layer_method of '{layer_method}' is not supported.  "
                                      "Please use 'dir.d' or 'disable'.")
        for action, path in filters:
            combiner.add_layer_filter(action, path)
        combiner.combine(self.app_dir, hook_label="package")
        self._var_magic.meta["layers"] = combiner.layer_names_used

    @require_active_context
    def blocklist(self, patterns):
        # XXX: Rewrite explicitly blocklist '.git' dir, because '.git*' wasn't working here. :=(

        # For now we just delete files out the build directory.  Not sophisticated, but it works
        # Do we need relwalker here?  relwalk
        from fnmatch import fnmatch
        for (root, dirs, files) in os.walk(self.build_dir, topdown=True):
            for fn in files:
                path = os.path.join(root, fn)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or fn == pattern:
                        self.output.write(f"Blocked file: {path}  (pattern: {pattern})\n")
                        os.unlink(path)
                        break
            for d in list(dirs):
                path = os.path.join(root, d)
                for pattern in patterns:
                    if ("*" in pattern and fnmatch(path, pattern)) or d == pattern:
                        self.output.write(f"Blocked dir:  {path}  (pattern: {pattern})\n")
                        dirs.remove(d)
                        shutil.rmtree(path)
                        break

    @require_active_context
    def merge_local(self):
        # XXX:  Rename this "promote_local()" ?
        """
        Find everything in local, if it has a corresponding file in default, merge.
        """
        # XXX: No logging/reporting done here :-(
        merge_app_local(self.app_dir)
        # Cleanup anything remaining in local
        self.block_local(report=False)

    @require_active_context
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

    @require_active_context
    def update_app_conf(self, version: str = None, build: str = None):
        """ Update version and/or build in ``apps.conf`` """
        app_settings = [
            ("launcher", "version", version),
            ("install", "build", build),
        ]
        appconf_file = find_conf_in_layers(self.app_dir, "app.conf") or \
            os.path.join(self.app_dir, "default", "app.conf")

        self.output.write(f"Updating app.conf file:  {appconf_file}\n")
        with update_conf(appconf_file, make_missing=True) as conf:
            for (stanza, attr, value) in app_settings:
                new_value = self.expand_new_only(value)
                if value:
                    if stanza not in conf:
                        conf[stanza] = {}
                    if new_value:
                        self.output.write(f"\tUpdate app.conf:  [{stanza}] "
                                          f"{attr} = {new_value} "
                                          f"(From {value})\n")
                        value = new_value
                    else:
                        self.output.write(f"\tUpdate app.conf:  [{stanza}] "
                                          f"{attr} = {value}\n")
                    conf[stanza][attr] = value

    @require_active_context(mutable=False)
    def check(self):
        """ Run safety checks prior to building archive:

        1.  Set app name based on app.conf [package] id, if set.  Otherwise confirm that the package
            id and top-level folder names align.
        2.  Check for files or directories starting with ``.``, makes AppInspect very grumpy!
        """
        # Should this force a freeze?  (Disable if this breaks anything...)
        self.freeze("check")
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
                self.output.write("Set app name from app.conf:  "
                                  f"{self.app_name}\n")
                self.app_name = package_id
            elif package_id != self.app_name:
                self.output.write(f"Top-level folder does not match the "
                                  f"package id:  folder: {self.app_name} "
                                  f"package id: {package_id}\n")
                if target_splunkbase:
                    raise PackagingException("Aborting build due to app name and package id "
                                             "discrepancy for public app:  "
                                             f"{package_id} != {self.app_name}")

        for root, dirs, files in os.walk(self.app_dir):
            for items, t in [(dirs, "directory"), (files, "file")]:
                for name in items:
                    if name[0] == ".":
                        self.output.write(f"Found hidden {t}:  {root}/{name}\n")

    @require_active_context(mutable=False)
    def make_archive(self, filename, temp_suffix: str = ".tmp"):
        """ Create a compressed tarball of the build directory.
        """
        # type: (str) -> str
        self.freeze("make_archive")
        # if os.path.isfile(filename):
        #    raise ValueError(f"Destination file already exists:  {filename}")
        app_name = self.expand_var(self.app_name)
        if app_name != self.app_name:
            self.output.write(f"Expanding template {self.app_name} to final "
                              f"app name: {app_name}\n")

        new_filename = self.expand_new_only(filename)
        if new_filename:
            self.output.write(f"Creating archive:  {new_filename}  (Expanded "
                              f"from '{os.path.basename(filename)}'\n")
            filename = new_filename
        else:
            self.output.write(f"Creating archive:  {filename}\n")

        if self.predictable_mtime:
            normalize_directory_mtime(self.app_dir)

        with atomic_writer(filename, temp_name=temp_suffix) as tmp_filename:
            with tarfile.open(tmp_filename, mode="w:gz") as spl:
                spl.add(self.app_dir, arcname=self.app_name)
        return filename

    @require_active_context(mutable=False)
    def make_manifest(self, calculate_hash=True) -> AppManifest:
        """
        Create a manifest of the app's contents.
        """
        self.freeze("make_manifest")
        app_name = self.expand_var(self.app_name)
        manifest = AppManifest.from_filesystem(self.app_dir, name=app_name,
                                               calculate_hash=calculate_hash)
        manifest.source = self.src_path
        return manifest

    def freeze(self, caller_name):
        """
        Initiate a content freeze by restricting mutable methods.
        The "package_pre_archive" hook is invoked before freeze operation.
        Such hooks may choose to mutate the filesystem at ``app_dir``, the only
        assumption is that all work is done before the hook returns.

        Freeze can be safely called multiple times. ``caller_name`` is simply a
        label used in an exception message if the programmer screwed up.
        """
        if self._mutable:
            plugin_manager.hook.package_pre_archive(app_dir=Path(self.app_dir),
                                                    app_name=self.expand_var(self.app_name))
            # Forbid any additional internal changes to the package
            self._mutable = False
            self._frozen_by = caller_name

    def __enter__(self) -> AppPackager:
        self.build_dir = tempfile.mkdtemp("-ksconf-package-build")
        self._mutable = True
        if self.app_name == "." or "{{" in self.app_name:
            # Use a placeholder app name, otherwise build_dir == app_dir
            self.app_dir = os.path.join(self.build_dir, "app")
        else:
            self.app_dir = os.path.join(self.build_dir, self.app_name)
        self._var_magic = AppVarMagic(self.src_path, self.app_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class AppVarMagicException(KeyError):
    pass


class AppVarMagic:
    """ A lazy loading dict-like object to fetch things like app version and such on demand. """

    def __init__(self, src_dir, build_dir, meta=None):
        self._cache = {}
        self.src_dir = src_dir
        self.build_dir = build_dir
        self.meta = meta or {}

    def expand(self, value: str) -> str:
        """ A simple Jinja2 like ``{{VAR}}`` substitution mechanism. """
        def replace(match_obj):
            var = match_obj.group(1)
            return self[var]
        if value:
            value = str(value)
            return re.sub(r"\{\{\s*([\w_]+)\s*\}\}", replace, value)
        return value

    def git_single_line(self, *args):
        out = git_cmd(args, cwd=self.src_dir)
        if out.returncode != 0:
            return f"git-errorcode-{out.returncode}"
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

    def get_layers_list(self):
        """ List of ksconf layers used. """
        layers = sorted(self.meta.get("layers"))
        if layers:
            return f'__{"__".join(layers)}__'
        else:
            return ""

    def get_layers_hash(self):
        """ Build a unique hash representing the combination of ksconf layers used. """
        DIGITS = 16
        layers_string = self["layers_list"]
        if layers_string:
            h = hashlib.sha256(layers_string.encode("utf-8"))
            return h.hexdigest()[:DIGITS]
        else:
            return "0" * DIGITS

    # END Variable fetching functions.

    def list_vars(self):
        """ Return a list of (variable, description) available in this class. """
        for name in dir(self):
            if name.startswith("get_"):
                var = name[4:]
                doc = getattr(self, name).__doc__.strip()
                yield (var, doc)

    def __getitem__(self, item):
        if item not in self._cache:
            self._cache[item] = self._get_expanded_var(item)
        return self._cache[item]

    def _get_expanded_var(self, item):
        get_funct_name = "get_" + item
        if hasattr(self, get_funct_name):
            try:
                funct = getattr(self, get_funct_name)
                return funct()
            except AppVarMagicException as e:
                if is_debug():
                    raise e
                return f"VAR-{item}-ERROR"
        else:
            raise KeyError(item)
