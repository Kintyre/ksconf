# -*- coding: utf-8 -*-
"""
"""

from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from os import fspath
from pathlib import Path

from ksconf.app import AppInfo
from ksconf.archive import GenArchFile, extract_archive
from ksconf.conf.parser import PARSECONF_LOOSE, ConfType, conf_attr_boolean, parse_conf
from ksconf.util.file import file_hash

if sys.version_info < (3, 8):
    from typing import List
else:
    List = list


MANIFEST_HASH = "sha256"


class AppManifestContentError(Exception):
    pass


class AppManifestStorageError(Exception):
    pass


class AppManifestStorageInvalid(AppManifestStorageError):
    pass


@dataclass(order=True)
class AppManifestFile:
    path: str
    mode: int
    size: int
    hash: str = None

    def content_match(self, other):
        return self.hash == other.hash

    @classmethod
    def from_dict(cls, data: dict) -> "AppManifestFile":
        return cls(data["path"], data["mode"], data["size"], data["hash"])


@dataclass
class AppManifest:
    name: str = None
    hash_algorithm: str = field(default=MANIFEST_HASH)
    _hash: str = field(default=None, init=False)
    files: List[AppManifestFile] = field(default_factory=list)

    @property
    def hash(self):
        if self._hash is None:
            self.files.sort()
            self._hash = self._calculate_hash()
        return self._hash

    def _calculate_hash(self) -> str:
        """ Build unique hash based on file content """
        parts = []
        for f in sorted(self.files):
            parts.append(f"{f.hash} 0{f.mode:o} {f.path}")
        parts.insert(0, self.name)
        payload = "\n".join(parts)
        print(f"DEBUG:   {payload}")
        h = hashlib.new(self.hash_algorithm)
        h.update(payload.encode("utf-8"))
        return h.hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> "AppManifest":
        files = [AppManifestFile.from_dict(f) for f in data["files"]]
        o = cls(data["name"], hash_algorithm=data["hash_algorithm"], files=files)
        o._hash = data["hash"]
        return o

    def to_dict(self):
        d = {
            "name": self.name,
            "hash_algorithm": self.hash_algorithm,
            "hash": self.hash,
            "files": [asdict(f) for f in self.files]
        }
        return d

    @classmethod
    def from_archive(cls, archive: Path) -> "AppManifest":
        manifest = cls()
        app_names = set()
        h_ = hashlib.new(MANIFEST_HASH)

        def gethash(content):
            # h = hashlib.new(MANIFEST_HASH)
            h = h_.copy()
            h.update(content)
            return h.hexdigest()

        for gaf in extract_archive(archive):
            app, relpath = gaf.path.split("/", 1)
            app_names.add(app)
            hash = gethash(gaf.payload)
            f = AppManifestFile(relpath, gaf.mode, gaf.size, hash)
            manifest.files.append(f)
        if len(app_names) > 1:
            raise AppManifestContentError("Found multiple top-level app names!  "
                                          f"Archive {archive} contains apps {', '.join(app_names)}")
        manifest.name = app_names.pop()
        return manifest


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
    def from_dict(cls, data: dict) -> "StoredArchiveManifest":
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
            json.dump(data, fp)

    @classmethod
    def read_json_manifest(cls, manifest_file: Path):
        with open(manifest_file) as fp:
            data = json.load(fp)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls,
                  archive: Path,
                  manifest: AppManifest
                  ) -> "StoredArchiveManifest":
        """
        Construct instance from a tarball.
        """
        stat = archive.stat()

        hash = file_hash(archive, MANIFEST_HASH)
        o = cls(archive, stat.st_size, stat.st_mtime, hash)
        o._manifest = manifest
        return o

    @classmethod
    def from_manifest(cls,
                      archive: Path,
                      stored_file: Path) -> "StoredArchiveManifest":
        """
        Attempt to load as stored manifest from archive & stored manifest paths.
        If the archive has changed since the manifest was stored, then an
        exception will be raised indicating the reason for invalidation.
        """
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


def create_manifest_from_archive(archive_file: Path,
                                 manifest_file: Path,
                                 manifest: AppManifest):
    sam = StoredArchiveManifest.from_file(archive_file, manifest)
    sam.write_json_manifest(manifest_file)
    return sam


class ManifestManager:
    @staticmethod
    def get_stored_manifest_name(archive: Path):
        c = archive.with_name(f".{archive.name}.manifest")
        return c
        '''
        if c.exists():
            return c
        return None
        '''

    def manifest_from_archive(self,
                              archive: Path,
                              read_manifest=True,
                              write_manifest=True) -> AppManifest:
        manifest = None

        if read_manifest or write_manifest:
            manifest_file = self.get_stored_manifest_name(archive)

        if read_manifest and manifest_file.exists():
            try:
                sam = StoredArchiveManifest.from_manifest(archive, manifest_file)
                manifest = sam.manifest
            except AppManifestStorageError as e:
                print(f"WARN:   loading stored manifest failed:  {e}")

        if manifest is None:
            print(f"Calculating manifest for {archive}")
            manifest = AppManifest.from_archive(archive)

            if write_manifest:
                create_manifest_from_archive(archive, manifest_file, manifest)

        return manifest
