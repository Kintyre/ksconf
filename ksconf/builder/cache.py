from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path, PurePath
from shutil import copy2, rmtree
from typing import List

from ksconf.builder import BuildCacheException
from ksconf.util.file import file_hash

# Finger print functions for a FileSet operations


def fingerprint_hash(path: Path) -> dict:
    return {
        "hash": file_hash(path)
    }


def fingerprint_stat(path: Path) -> dict:
    stat = path.stat()
    return {
        "mtime": stat.st_mtime,
        "ctime": stat.st_ctime,
        "size": stat.st_size,
    }


class FileSet:
    """ A collection of fingerprinted files.

    Currently the fingerprint is only a SHA256 hash.

    Two constructors are provided for building an instance from either files that
    live on the filesystem, via :py:meth:`from_filesystem` or from a persisted
    cached record available from the :py:meth:`from_cache`.
    The filesystem version actively reads all inputs files at object creation
    time, so this can be costly, especially if repeated.
    """
    # XXX: Do we need both files (set), and file_meta (dict)?  Try to make this work with just files_meta
    __slots__ = ["files", "files_meta", "get_fingerprint"]

    def __init__(self, fingerprint=fingerprint_hash):
        self.files = set()
        self.files_meta = {}
        self.get_fingerprint = fingerprint

    def __eq__(self, other: FileSet) -> bool:
        return self.files_meta == other.files_meta

    def __ne__(self, other: FileSet) -> bool:
        return self.files_meta != other.files_meta

    '''
    def __iadd__(self, other):
        self.files.update(other.files)
        self.files_meta.update(other.files_meta)

    def __add__(self, other):
        combined = FileSet()
        for item in (self, other):
            combined.files.update(item.files)
            combined.files_meta.update(item.files_meta)
        return combined
    '''

    def __iter__(self):
        return iter(self.files)

    def __len__(self):
        return len(self.files)

    @classmethod
    def from_filesystem(cls, root: Path, files: List[str] = None) -> FileSet:
        """
        Create a new FileSet instance based on a filesystem location.
        If ``files`` is None, then the entire directory is added recursively.
        """
        instance = cls()
        root = Path(root)
        if files is None:
            # Add root recursively
            instance.add_glob(root, "**/*")
            return instance
        for file_name in files:
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

    def add_file(self, root: Path, relative_path: str):
        """ Add a simple relative path to a file to the FileSet. """
        relative_path = PurePath(relative_path)
        p = root / relative_path
        if not p.is_file():
            if p.is_dir():
                # Audience: Exception text relevant to from_filesystem() caller
                raise BuildCacheException(
                    f"Expected file '{p}' is actually a directory.  If this is "
                    "correct indicate a directory with a trailing slash: "
                    f"'{p}/'")
            raise BuildCacheException(f"Missing expected file {p}")
        fp = self.get_fingerprint(p)
        self.files.add(relative_path)
        self.files_meta[relative_path] = fp

    def add_glob(self, root: Path, pattern: str):
        """ Recursively add all files matching glob pattern. """
        for p in root.glob(pattern):
            if p.is_file():
                relative_path = p.relative_to(root)

                fp = self.get_fingerprint(p)
                self.files.add(relative_path)
                self.files_meta[relative_path] = fp

    def copy_all(self, src_dir: Path, dest_dir: Path):
        """ Copy a the given set of files from one location to another. """
        src_dir = Path(src_dir)
        dest_dir = Path(dest_dir)
        for file_name in self.files:
            src = src_dir / file_name
            dest = dest_dir / file_name
            if not dest.parent.is_dir():
                dest.parent.mkdir(parents=True)
            copy2(src, dest)


class CachedRun:
    __slots__ = ["root", "config_file", "cache_dir", "_info", "_settings", "_state"]

    STATE_NEW = "new"
    STATE_EXISTS = "exists"
    STATE_TAINT = "taint"
    STATE_DISABLED = "disabled"

    _timestamp_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self, root: Path):
        self.root = root
        self.config_file = self.root / "cache.json"
        self.cache_dir = self.root / "data"
        self._settings = {}
        self._info = {}
        self._state = self.STATE_NEW

        if not self.cache_dir.is_dir():
            self.cache_dir.mkdir(parents=True)
        elif self.config_file.is_file() and self.cache_dir.is_dir():
            self._state = self.STATE_EXISTS

    def set_settings(self, cache_settings):
        self._settings.update(cache_settings)

    @property
    def cached_inputs(self):
        return FileSet.from_cache(self._info["inputs"])

    @property
    def cached_outputs(self):
        return FileSet.from_cache(self._info["outputs"])

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
            raise   # XXX: For initial testing
            # If anything about the info/settings were missing; assume expired
            return True

    @property
    def is_disabled(self):
        return self._state == self.STATE_DISABLED

    def inputs_identical(self, inputs: FileSet) -> bool:
        return self.cached_inputs == inputs

    def dump(self):
        def map_keys(d):
            return {str(k): v for k, v in d.items()}
        mode = "w"
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
        info["timestamp"] = datetime.strptime(data["timestamp"],
                                              self._timestamp_format)
        for state_type, value in data["state"].items():
            info[state_type] = map_keys(value)
        self._settings = data["settings"]
        self._info = info

    def set_cache_info(self, type: str, data: FileSet):
        assert type in ("inputs", "outputs")
        self._info[type] = data.files_meta

    def rename(self, dest):
        if dest.is_dir():
            rmtree(dest)
        self.root.rename(dest)
        # Update root incase any other operations need to take place
        self.root = dest

    def taint(self):
        cf = self.config_file
        if cf.exists():
            cf.unlink()
        self._state = self.STATE_TAINT

    def disable(self):
        self._state = self.STATE_DISABLED
