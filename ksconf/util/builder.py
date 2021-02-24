# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

"""


Cache build requirements:

    * Caching mechanism should inspet 'inputs' (collect file hashes) to determine if any content has changed.  If input varies, then command should be re-run.
    * Command (decorated function) should be generally unaware of all other details of build process, and it should *ONLY* be able to see files listed in "inputs"
    * Allow caching to be fully disabled (run in-place with no dir proxying) for CI/CD
    * Cache should have allow a timeout paramater




decorator used to implement caching:
    * decorator args:
        * inputs:       list or glob
        * outputs       (do we need this, can we just detect this??) --- Default to "." (everything)
        * timeout=0     Seconds before cache should be considered stale
        * name=None     If not given, default to the short name of the function.  (Cache "slot"), must be filesystem safe]
"""

import json
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path, PurePath
from shutil import copy2, rmtree

from ksconf.ext.six import PY2, text_type
from ksconf.util.file import file_hash

try:
    from tempfile import TemporaryDirectory
except ImportError:
    from backports.tempfile import TemporaryDirectory


if sys.version_info < (3, 6):
    # Make these standard functions receive strings rather than Path objects
    from ksconf.util.file import pathlib_compat
    copy2 = pathlib_compat(copy2)
    rmtree = pathlib_compat(rmtree)
    TemporaryDirectory = pathlib_compat(TemporaryDirectory)



class BuildCacheException(Exception):
    pass



class BuildStep(object):
    __slots__ = ["build_path", "source_path", "config", "verbosity"]

    def __init__(self, build, source=None):
        self.build_path = build
        self.source_path = source
        self.config = {}
        self.verbosity = 0

    def alternate_path(self, path):
        """ Create a new BuildStep instance with only 'build_path' altered. """
        cls = self.__class__
        instance = cls(path)
        for slot in cls.__slots__:
            if slot != "build_path":
                setattr(instance, slot, getattr(self, slot))
        return instance


class _FileSet(object):
    # XXX: setup slots?
    def __init__(self):
        # self.root = None
        self.files = set()
        self.files_meta = {}

    def __eq__(self, other):
        # type: (_FileSet) -> bool
        return self.files_meta == other.files_meta

    def __iter__(self):
        return iter(self.files)

    @classmethod
    def from_filesystem(cls, root, files):
        instance = cls()
        root = Path(root)
        for file_name in files:
            # XXX: Support globs
            if file_name.endswith("/"):
                # Recursive directory walk
                instance.add_glob(root, file_name + "**/*")
            elif "*" in file_name:
                instance.add_glob(root, file_name)
            else:
                instance.add_file(root, file_name)
        return instance

    @classmethod
    def from_cache(cls, data):
        instance = cls()
        for file_name, meta in data.items():
            file_name = PurePath(file_name)
            instance.files.add(file_name)
            instance.files_meta[file_name] = meta
        return instance

    def add_file(self, root, relative_path):
        relative_path = PurePath(relative_path)
        p = root / relative_path
        if not p.is_file():
            if p.is_dir():
                raise BuildCacheException("Expected file {} is a directory.  "
                                          "Please make directories with a trailing '/'".format(p))
            raise BuildCacheException("Missing expected file {}".format(p))
        self.files.add(relative_path)
        self.files_meta[relative_path] = self.get_fingerprint(p)

    def add_glob(self, root, relative_path):
        """ Recursively add all files matching glob pattern. """
        for p in root.glob(relative_path):
            if not p.is_file():
                continue
            relative_path = p.relative_to(root)
            self.files.add(relative_path)
            self.files_meta[relative_path] = self.get_fingerprint(p)

    @staticmethod
    def get_fingerprint(path):
        return {
            "hash": file_hash(path)
        }

    def copy_all(self, src_dir, dest_dir):
        src_dir = Path(src_dir)
        dest_dir = Path(dest_dir)
        for file_name in self.files:
            src = src_dir / file_name
            dest = dest_dir / file_name
            if not dest.parent.is_dir():
                dest.parent.mkdir()
            copy2(src, dest)


class CachedRun(object):
    __slots__ = ["root", "config_file", "cache_dir", "_info", "_settings", "_state"]

    STATE_NEW = "new"
    STATE_EXISTS = "exists"

    _timestamp_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self, root):
        # type: Path
        self.root = root
        self.config_file = self.root / "cache.json"
        self.cache_dir = self.root / "data"
        self._settings = {}
        self._info = {}
        self._state = self.STATE_NEW
        # self._inputs = []
        # self._outputs = []

        if not self.cache_dir.is_dir():
            self.cache_dir.mkdir(parents=True)
        elif self.config_file.is_file() and self.cache_dir.is_dir():
            self._state = self.STATE_EXISTS

    def set_settings(self, cache_settings):
        self._settings.update(cache_settings)

    '''
    def set_lists(self, inputs, outputs):
        self._inputs = inputs
        self._outputs = outputs
    @property
    def config_file():
        return os.path.join(self.root, "cache.json")
    @property
        return os.path.join(self.root, "data")
    '''

    @property
    def cached_inputs(self):
        return _FileSet.from_cache(self._info["inputs"])

    @property
    def cached_outputs(self):
        return _FileSet.from_cache(self._info["outputs"])

    @property
    def filesystem_outputs(self):
        return _FileSet.from_filesystem(self.cache_dir, self._outputs)

    '''
    @property
    def filesystem_inputs(self):
        return _FileSet.from_filesystem(self.source_dir, self._inputs)
    '''

    @property
    def exists(self):
        return self._state in (self.STATE_EXISTS,)

    @property
    def is_new(self):
        return self._state == self.STATE_NEW

    @property
    def is_expired(self):

        timeout = self._settings["timeout"]
        if timeout is None:
            return False
        try:
            create_time = self._info["timestamp"]
            timeout = timedelta(seconds=timeout)
            expired = create_time + timeout
            return datetime.now() > expired
        except KeyError:  # no cover
            raise   # For initial testing
            # If anything about the info/settings were missing; assume expired
            return True

    def inputs_identical(self, inputs):
        # type: _FileSet
        return self.cached_inputs == inputs

    def dump(self):
        def map_keys(d):
            return {text_type(k): v for k, v in d.items()}
        mode = "wb" if PY2 else "w"
        meta = dict(self._info)
        inputs = meta.pop("inputs")
        outputs = meta.pop("outputs")
        data = {
            "settings": self._settings,
            "timestamp": datetime.now().strftime(self._timestamp_format),
            "meta": meta,
            "state": {
                "inputs": map_keys(inputs),
                "outputs": map_keys(outputs),
            },
        }
        with self.config_file.open(mode) as f:
            json.dump(data, f, indent=2)

    def load(self):
        def map_keys(d):
            return {Path(k): v for k, v in d.items()}
        with self.config_file.open() as f:
            data = json.load(f)
        info = {}
        info.update(data["meta"])
        info["timestamp"] = datetime.strptime(data["timestamp"], self._timestamp_format)
        for state_type, value in data["state"].items():
            info[state_type] = map_keys(value)
        self._settings = data["settings"]
        self._info = info

    def set_cache_info(self, type, data):
        # type: str, _FileSet
        assert type in ("inputs", "outputs")
        self._info[type] = data.files_meta

    def copy_inputs_from(self, src_path, files):
        fs = _FileSet.from_filesystem(src_path, files)
        fs.copy_all(self.cache_dir)

    def copy_output_to(self, dest_path):
        self.cached_outputs.copy_all(self.cache_dir, dest_path)

    def rename(self, dest):
        if dest.is_dir():
            rmtree(dest)
        self.root.rename(dest)
        # Update root incase any other operations need to take place
        self.root = dest


class BuildManager(object):

    def __init__(self):
        self.source_path = None
        self.build_path = None
        self.cache_path = None
        self._cache_enabled = True

    def get_build_step(self):
        step = BuildStep(self.build_path, self.source_path)
        return step

    def set_folders(self, source_path, build_path):
        self.source_path = Path(source_path)
        self.build_path = Path(build_path)
        self.cache_path = self.build_path.with_suffix(".cache")

    def get_cache_info(self, name):
        path = self.cache_path / name
        cache_info = CachedRun(path)
        return cache_info

    def cache(self, inputs, outputs=".", timeout=None, name=None):
        """ function decorator """
        name_ = name
        cache_settings = {
            "name": name,
            "inputs": inputs,
            "outputs": outputs,
            "timeout": timeout,
        }

        def decorator(f):
            # nonlocal name
            if name_ is None:
                name = f.__name__.split(".")[-1]

            @wraps(f)
            def wrapper(build_step):
                # args: BuildStep -> None
                cache = self.get_cache_info(name)
                # Once the first cached build step is executed, then block access to the source path
                build_step.source_path = None
                if cache.exists:
                    cache.load()
                # Always use the most up-to-date value for timeout
                cache.set_settings({"timeout": timeout})
                # TODO: Validate that cache settings match; for example if 'outputs' changes then files could be skipped
                # TODO: Check for cache tampering (confirm that existing files haven't been modified); user requestable
                current_inputs = _FileSet.from_filesystem(self.source_path, inputs)
                # Determine if previous cache entry exists, and if the inputs haven't changed
                if cache.exists and cache.inputs_identical(current_inputs) and not cache.is_expired:
                    # Cache HIT:  Reuse cache, by simply copying the outputs to the build folder
                    cache.copy_output_to(self.build_path)
                else:
                    # Cache MISS: Prepare to call the wrapped function
                    # 1. √ Make temporary location
                    # 2. √ Copy inputs to temp location
                    # 3. √ Run wrapped functionality
                    # 4. √ Expand output into FileSet (Collect)
                    # 5. √ Store metadata (inputs/outputs/...) to JSON
                    # 6. √ Copy output to real build folder

                    # Make temporary folder for executing wrapped function
                    with TemporaryDirectory(dir=self.cache_path,
                                            prefix="{}-tmp-".format(name)) as temp_dir:
                        # NOTE: Make a 't' dir under the temp folder so that the cache.rename() doesn't remove the
                        #       folder managed by TemporaryDirectory, which it doesn't like.
                        temp_dir = Path(temp_dir) / "t"
                        final_cache_root = cache.root
                        cache = CachedRun(temp_dir)
                        alt_bs = build_step.alternate_path(cache.cache_dir)
                        # XXX: Copy any other settings from the original 'build_step' to our copied version
                        # Collect inputs from the source directory and copy them to the temporary directory
                        fs_inputs = _FileSet.from_filesystem(self.source_path, inputs)
                        fs_inputs.copy_all(self.source_path, cache.cache_dir)
                        try:
                            # Run wrapped function
                            ret = f(alt_bs)
                            if ret is not None:
                                raise NotImplementedError("A return value not supported for cached build steps")
                        except Exception:
                            # XXX: More error handling here.  Add custom exception class
                            raise
                        # TODO: Check for change to inputs.  This could lead to nondeterministic results
                        fs_outputs = _FileSet.from_filesystem(cache.cache_dir, outputs)
                        # Store input/output fingerprint to the internal cache state and persist to disk
                        cache.set_settings(cache_settings)
                        cache.set_cache_info("inputs", fs_inputs)
                        cache.set_cache_info("outputs", fs_outputs)
                        cache.dump()
                        # Copy output files to real build directory
                        fs_outputs.copy_all(cache.cache_dir, self.build_path)
                        cache.rename(final_cache_root)
                # No return (on purpose); as we don't want to track extra state

            if self._cache_enabled:
                wrapper.inputs = inputs
                wrapper.outputs = outputs
                wrapper.timeout = timeout
                wrapper.name = name
                wrapper.cached = True
                return wrapper
            else:
                # No caching, just return the original function
                f.cached = False
                return f

        return decorator
