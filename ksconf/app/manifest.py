# -*- coding: utf-8 -*-
""" Splunk App content inventory and signature management

"""

from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import json
from dataclasses import asdict, dataclass, field
from os import fspath
from pathlib import Path, PurePosixPath
from typing import Iterable

from ksconf.archive import extract_archive
from ksconf.compat import List
from ksconf.consts import MANIFEST_HASH, UNSET
from ksconf.util.file import file_hash, relwalk


class AppArchiveError(Exception):
    pass


class AppArchiveContentError(Exception):
    """ Problem with the contents of an archive """
    pass


class AppManifestStorageError(Exception):
    pass


class AppManifestStorageInvalid(AppManifestStorageError):
    pass


@dataclass(order=True)
class AppManifestFile:
    path: PurePosixPath
    mode: int
    size: int
    hash: str = None

    def content_match(self, other):
        return self.hash == other.hash

    def to_dict(self):
        d = asdict(self)
        d["path"] = fspath(self.path)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AppManifestFile:
        return cls(PurePosixPath(data["path"]), data["mode"], data["size"], data["hash"])


@dataclass
class AppManifest:
    name: str = None
    source: str = None
    hash_algorithm: str = field(default=MANIFEST_HASH)
    _hash: str = field(default=UNSET, init=False)
    files: List[AppManifestFile] = field(default_factory=list)

    def __eq__(self, other: AppManifest) -> bool:
        if self.name != other.name or self.hash != other.hash:
            return False
        return sorted(self.files) == sorted(other.files)

    @property
    def hash(self):
        # How do we trigger an update if files is updated?  Should we make the caller worry about this?  Maybe call a reset() method?
        # Should we convert the list to a tuple as soon as hash is calculated for the first time, then require cloning to make further modifications?
        if self._hash is UNSET:
            self._hash = self._calculate_hash()
        return self._hash

    def _calculate_hash(self) -> str:
        """ Build unique hash based on file content """
        # Path sort order notes.  Sorting based on Path objects is different
        # than textual sorting, consider:
        #   README.txt
        #   README/inputs.conf.spec
        # Sorting based on path is equivalent to sorting tuples of path components
        # Like doing sort(key=lambda s: s.path.split("/"))
        parts = []
        for f in sorted(self.files):
            # If one or more hash is None, then refuse to calculate hash
            if f.hash is None:
                return None
            parts.append(f"{f.hash} 0{f.mode:o} {'/'.join(f.path.parts)}")
        parts.insert(0, self.name)
        payload = "\n".join(parts)
        h = hashlib.new(self.hash_algorithm)
        h.update(payload.encode("utf-8"))
        return h.hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> AppManifest:
        files = [AppManifestFile.from_dict(f) for f in data["files"]]
        o = cls(data["name"], source=data["source"],
                hash_algorithm=data["hash_algorithm"], files=files)
        o._hash = data["hash"]
        return o

    def to_dict(self):
        d = {
            "name": self.name,
            "source": self.source,
            "hash_algorithm": self.hash_algorithm,
            "hash": self.hash,
            "files": [f.to_dict() for f in self.files]
        }
        return d

    @classmethod
    def from_archive(cls, archive: Path,
                     calculate_hash=True) -> AppManifest:
        """
        Create as new AppManifest from a tarball.  Set ``calculate_hash`` as
        False when only a file listing is needed.
        """
        manifest = cls(source=fspath(archive))
        app_names = set()
        archive = Path(archive)

        if calculate_hash:
            h_ = hashlib.new(cls.hash_algorithm)

            def gethash(content):
                h = h_.copy()
                h.update(content)
                return h.hexdigest()
        else:
            def gethash(_):
                return None

        for gaf in extract_archive(archive, lambda _: calculate_hash):
            app, relpath = gaf.path.split("/", 1)
            app_names.add(app)
            hash = gethash(gaf.payload)
            f = AppManifestFile(PurePosixPath(relpath), gaf.mode, gaf.size, hash)
            manifest.files.append(f)
        if len(app_names) > 1:
            raise AppArchiveContentError("Found multiple top-level app names!  "
                                         f"Archive {archive} contains apps {', '.join(app_names)}")
        manifest.name = app_names.pop()
        return manifest

    @classmethod
    def from_filesystem(cls, path: Path,
                        name: str = None,
                        follow_symlinks=False,
                        calculate_hash=True) -> AppManifest:
        """
        Create as new AppManifest from an existing directory structure.
        Set ``calculate_hash`` as False when only a file listing is needed.
        """
        path = Path(path)
        if name is None:
            name = path.name
        manifest = cls(name, source=path)
        h_ = hashlib.new(cls.hash_algorithm)

        for (root, _, files) in relwalk(path, followlinks=follow_symlinks):
            root_path = PurePosixPath(root)
            for file_name in files:
                rel_path: PurePosixPath = root_path.joinpath(file_name)
                full_path: Path = path.joinpath(root, file_name)
                st = full_path.stat()
                amf = AppManifestFile(rel_path, st.st_mode & 0o777, st.st_size)
                if calculate_hash:
                    h = h_.copy()
                    h.update(full_path.read_bytes())
                    amf.hash = h.hexdigest()
                    del h
                manifest.files.append(amf)
        return manifest

    def find_local(self) -> Iterable[AppManifestFile]:
        for f in self.files:
            if f.path.parts[0] == "local" or f.path.name == "local.meta":
                yield f

    def check_paths(self):
        """ Check for dangerous paths in the archive. """
        for file in self.files:
            path = file.path
            if path.is_absolute():
                raise AppArchiveContentError(f"Found an absolute path {file.path}")
            if ".." in path.parts or path.parts[0].startswith("~"):
                raise AppArchiveContentError(f"Found questionable path manipulation in '{file.path}'")


@dataclass
class StoredArchiveManifest:
    """
    Stored manifest for a tarball.  Typically the manifest file lives in the
    same directory as the archive.  Details around the naming, storage, and
    clean up of these persistent manifest files are managed by the caller.
    """
    archive: Path
    size: int
    mtime: float
    hash: str
    _manifest_dict: dict = field(init=False)
    _manifest: AppManifest = field(init=False, default=None)

    @property
    def manifest(self) -> AppManifest:
        # Lazy load the full manifest details later (after size/mtime/hash have been confirmed)
        if self._manifest is None:
            if self._manifest_dict:
                try:
                    self._manifest = AppManifest.from_dict(self._manifest_dict)
                except KeyError as e:
                    raise AppManifestStorageError(f"Error loading manifest {e}")

        return self._manifest

    @classmethod
    def from_dict(cls, data: dict) -> StoredArchiveManifest:
        o = cls(Path(data["archive"]), data["size"], data["mtime"], data["hash"])
        o._manifest_dict = data["manifest"]
        return o

    def to_dict(self):
        return {
            "archive": fspath(self.archive),
            "size": self.size,
            "mtime": self.mtime,
            "hash": self.hash,
            "manifest": self.manifest.to_dict(),
        }

    def write_json_manifest(self, manifest_file: Path):
        data = self.to_dict()
        with open(manifest_file, "w") as fp:
            json.dump(data, fp, indent=1)

    @classmethod
    def read_json_manifest(cls, manifest_file: Path) -> StoredArchiveManifest:
        with open(manifest_file) as fp:
            data = json.load(fp)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls,
                  archive: Path,
                  manifest: AppManifest
                  ) -> StoredArchiveManifest:
        """
        Construct instance from a tarball.
        """
        stat = archive.stat()

        hash = file_hash(archive, MANIFEST_HASH)
        o = cls(archive, stat.st_size, stat.st_mtime, hash)
        o._manifest = manifest
        return o

    @classmethod
    def from_json_manifest(cls,
                           archive: Path,
                           stored_file: Path) -> StoredArchiveManifest:
        """
        Attempt to load as stored manifest from archive & stored manifest paths.
        If the archive has changed since the manifest was stored, then an
        exception will be raised indicating the reason for invalidation.
        """
        # XXX: Optimization: tests if archive is newer than stored_file.  No need to open/parse JSON.
        if not stored_file:
            raise AppManifestStorageInvalid("No stored manifest found")

        try:
            stored = cls.read_json_manifest(stored_file)

            if stored.archive != archive:
                raise AppManifestStorageInvalid(f"Archive name differs: {stored.archive!r} != {archive!r}")
            stat = archive.stat()
            if stored.size != stat.st_size:
                raise AppManifestStorageInvalid(f"Archive file size differs:  {stored.size} != {stat.st_size}")
            if abs(stored.mtime - stat.st_mtime) > 0.1:
                raise AppManifestStorageInvalid(f"Archive file mtime differs: {stored.mtime} vs {stat.st_mtime}")
        except (ValueError, KeyError) as e:
            raise AppManifestStorageError(f"Unable to load stored manifest due to {e}")
        return stored


def get_stored_manifest_name(archive: Path) -> Path:
    """
    Calculate the name of the stored manifest file based on ``archive``.
    """
    c = archive.with_name(f".{archive.name}.manifest")
    return c


def create_manifest_from_archive(
        archive_file: Path,
        manifest_file: Path,
        manifest: AppManifest) -> StoredArchiveManifest:
    """
    Create a new stored manifest file based on a given archive.
    """
    if manifest_file is None:
        manifest_file = get_stored_manifest_name(archive_file)
    sam = StoredArchiveManifest.from_file(archive_file, manifest)
    sam.write_json_manifest(manifest_file)
    return sam


def load_manifest_for_archive(
        archive: Path,
        manifest_file: Path = None,
        read_manifest=True,
        write_manifest=True) -> AppManifest:
    """
    Load manifest for ``archive`` and create a stored copy of the manifest in
    ``manifest_file``.  On subsequent calls the manifest data stored to disk
    will be reused assuming ``manifest_file`` is up-to-date.

    File modification time and size are used to determine if ``archive`` has
    been changed since the ``manifest_file`` was written.

    If no ``manifest_file`` is provided, the default manifest naming convention
    will be applied where the ``manifest_file`` is stored in the same directory
    as ``archive``.
    """
    # XXX: Add optimization to check if archive is newer than manifest_file, assume old
    archive = Path(archive)
    manifest = None

    if manifest_file is None and read_manifest or write_manifest:
        manifest_file = get_stored_manifest_name(archive)

    if read_manifest and manifest_file.exists():
        try:
            sam = StoredArchiveManifest.from_json_manifest(archive, manifest_file)
            manifest = sam.manifest
        except AppManifestStorageError as e:
            print(f"WARN:   loading stored manifest failed:  {e}")

    if manifest is None:
        # print(f"Calculating manifest for {archive}")
        manifest = AppManifest.from_archive(archive)

        # We assume that a previously stored manifest has already undergone the
        # path check.  Checks should be redone from within the extraction process.
        manifest.check_paths()

        if write_manifest:
            create_manifest_from_archive(archive, manifest_file, manifest)

    return manifest
