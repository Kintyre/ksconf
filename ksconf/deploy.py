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

from ksconf.archive import GenArchFile, extract_archive
from ksconf.util.file import file_hash

if sys.version_info < (3, 8):
    from typing import List
else:
    List = list


MANIFEST_HASH = "sha256"


def _get_json(path) -> dict:
    with open(path) as fp:
        return json.load(fp)


class AppManifestContentError(Exception):
    pass


class AppManifestCacheError(Exception):
    pass


class AppManifestCacheInvalid(AppManifestCacheError):
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


@dataclass
class CachedArchiveManifest:
    """
    Cached manifest for a tarball.  Typically the cache file lives along side the archive.
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
                    raise AppManifestCacheError(f"Error loading manifest {e}")

        return self._manifest

    @classmethod
    def from_dict(cls, data: dict) -> "CachedArchiveManifest":
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

    @classmethod
    def from_file(cls,
                  path: Path,
                  manifest: AppManifest
                  ) -> "CachedArchiveManifest":
        stat = path.stat()

        hash = file_hash(path, MANIFEST_HASH)
        o = cls(path, stat.st_size, stat.st_mtime, hash)
        o._manifest = manifest
        return o


class ManifestManager:

    @staticmethod
    def filter_archive(gaf: GenArchFile):
        if Path(gaf.path).name in (".ksconf_sideload.json"):
            return False
        return True

    @staticmethod
    def find_archive_cache(archive: Path):
        c = archive.with_name(f".{archive.name}.cache")
        return c
        '''
        if c.exists():
            return c
        return None
        '''

    @staticmethod
    def load_manifest_from_archive_cache(archive: Path,
                                         cache_file: Path
                                         ) -> AppManifest:
        """ Return manifest, reason for cache invalidation. """
        if not cache_file:
            raise AppManifestCacheInvalid("No cache found")

        try:
            data = _get_json(cache_file)
            cache = CachedArchiveManifest.from_dict(data)

            if cache.archive != archive:
                raise AppManifestCacheInvalid(f"Archive name differs: {cache.archive!r} != {archive!r}")
            stat = archive.stat()
            if cache.size != stat.st_size:
                raise AppManifestCacheInvalid(f"Archive file size differs:  {cache.size} != {stat.st_size}")
            if abs(cache.mtime - stat.st_mtime) > 0.1:
                raise AppManifestCacheInvalid(f"Archive file mtime differs: {cache.mtime} vs {stat.st_mtime}")
        except (ValueError, KeyError) as e:
            raise AppManifestCacheError(f"Unable to load cache due to {e}")
        return cache.manifest

    @staticmethod
    def save_manifest_from_archive(archive_file: Path,
                                   cache_file: Path,
                                   manifest: AppManifest):

        manifest_archive = CachedArchiveManifest.from_file(archive_file, manifest)
        data = manifest_archive.to_dict()
        with open(cache_file, "w") as fp:
            json.dump(data, fp)

    @classmethod
    def build_manifest_from_archive(cls, archive: Path) -> AppManifest:
        manifest = AppManifest()
        app_names = set()
        h_ = hashlib.new(MANIFEST_HASH)

        def gethash(content):
            # h = hashlib.new(MANIFEST_HASH)
            h = h_.copy()
            h.update(content)
            return h.hexdigest()

        for gaf in extract_archive(archive, cls.filter_archive):
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

    def manifest_from_archive(self,
                              archive: Path,
                              read_cache=True,
                              write_cache=True) -> AppManifest:
        manifest = None

        if read_cache or write_cache:
            cache_file = self.find_archive_cache(archive)

        if read_cache and cache_file.exists():
            try:
                manifest = self.load_manifest_from_archive_cache(archive, cache_file)
            except AppManifestCacheError as e:
                print(f"WARN:   loading existing cache failed:  {e}")

        if manifest is None:
            print(f"Calculating manifest for {archive}")
            manifest = self.build_manifest_from_archive(archive)

            if write_cache:
                self.save_manifest_from_archive(archive, cache_file, manifest)

        return manifest
