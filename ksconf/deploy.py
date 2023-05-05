# -*- coding: utf-8 -*-
"""
"""

from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ksconf.archive import GenArchFile, extract_archive

if sys.version_info < (3, 8):
    from types import List
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
    hash: str = field(init=False)

    def content_match(self, other):
        return self.hash == other.hash

    @classmethod
    def from_dict(cls, data: dict) -> "AppManifestFile":
        o = cls(data["path"], data["mode"], data["mtime"])
        if "hash" in data:
            o.hash = data["hash"]
        return o


@dataclass
class AppManifest:
    name: str = None
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
        for f in self.files:
            parts.append(f"{f.path} 0{f.mode:o} {f.hash}")
        parts.sort()
        parts.insert(0, self.name)
        payload = "\n".join(parts)
        print(f"DEBUG:   {payload}")
        h = hashlib.new(MANIFEST_HASH)
        h.update(payload.encode("utf-8"))
        return h.hexdigest()

    @classmethod
    def from_dict(cls, data: dict) -> "AppManifest":
        files = [AppManifestFile.from_dict(f) for f in data["files"]]
        return cls(data["name"], data["path"], files=files)

    def to_dict(self):
        d = {
            "name": self.name,
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
                    self._manifest = AppManifestFile.from_dict(self._manifest_dict)
                except KeyError as e:
                    raise AppManifestCacheError(f"Error loading manifest {e}")

        return self._manifest

    @classmethod
    def from_dict(cls, data: dict) -> "CachedArchiveManifest":
        o = cls(data["archive"], data["size"], data["mtime"], data["hash"])
        o._manifest_dict = data["manifest"]
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

            if cache.archive != archive.name:
                return AppManifestCacheInvalid("Archive name differs")
            stat = archive.stat()
            if cache.size != stat.st_size:
                return AppManifestCacheInvalid("Archive file size differs")
            if abs(cache.mtime - stat.st_mtime) > 0.1:
                return AppManifestCacheInvalid("Archive file mtime differs")
        except (ValueError, KeyError) as e:
            return AppManifestCacheError(f"Unable to load cache due to {e}")
        return cache.manifest

    @staticmethod
    def save_manifest_from_archive(cache_file: Path,
                                   manifest: AppManifest):
        data = manifest.to_dict()
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
            print(f"CONTENT:   {content!r}")
            h.update(content)
            return h.hexdigest()

        for gaf in extract_archive(archive, cls.filter_archive):
            app, relpath = gaf.path.split("/", 1)
            app_names.add(app)
            f = AppManifestFile(relpath, gaf.mode, gaf.size)
            f.hash = gethash(gaf.payload)
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
                self.save_manifest_from_archive(cache_file, manifest)

        return manifest
