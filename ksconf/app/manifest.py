# -*- coding: utf-8 -*-
""" Splunk App content inventory and signature management

"""

from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import json
from dataclasses import asdict, dataclass, field
from os import fspath
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Optional, Union

from ksconf.archive import extract_archive
from ksconf.compat import List
from ksconf.consts import _UNSET, MANIFEST_HASH, UNSET
from ksconf.util.file import atomic_open, file_hash, relwalk


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
    """
    Manifest entry for a single file contained within an app.

    You probably don't want this class.  Use :py:class:`AppManifest` instead.
    """
    path: PurePosixPath
    mode: int
    size: int
    hash: Optional[str] = None

    def content_match(self, other: AppManifestFile):
        return self.hash == other.hash

    def to_dict(self):
        d = asdict(self)
        d["mode"] = f"0{self.mode:03o}"
        d["path"] = fspath(self.path)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AppManifestFile:
        # v1: 'mode' is int
        # v2: 'mode' is octal string
        mode = data["mode"]
        try:
            mode = int(mode, 8)
        except TypeError:
            if not isinstance(mode, int):
                raise ValueError(f"Unable to handle mode value {mode!r}")
        return cls(PurePosixPath(data["path"]), mode, data["size"], data["hash"])


FileFilterFunction = Callable[[PurePosixPath], bool]


@dataclass
class AppManifest:
    """
    Manifest of a Splunk app.  It contains the signatures of contained files and
    optionally a hash signature of app content.

    This is quite very different than a tarball hash, which includes "noise",
    like file modification time and possibly tarball creation time.  These
    factors make comparison more expensive.  The goal of this class is the
    ability to capture an app's content "fingerprint" and quickly determine if
    another app is the same or not.  And to compare apps across equally between
    tarballs, expanded folders, or a serialized capture at a point in time.

    Build instances using:

    * :py:meth:`from_tarball` - from a Splunk ``.spl`` or ``.tar.gz`` file.
    * :py:meth:`from_filesystem` - from an extracted Splunk app directory
    * :py:meth:`from_dict` - primarily for json serialization from :py:meth:`to_dict`.
    """
    name: Optional[str] = None
    source: Union[str, Path, None] = None
    hash_algorithm: str = field(default=MANIFEST_HASH)
    _hash: Union[str, _UNSET] = field(default=UNSET, init=False)
    files: List[AppManifestFile] = field(default_factory=list)

    def __eq__(self, other: AppManifest) -> bool:
        if self.name != other.name or self.hash != other.hash:
            return False
        return sorted(self.files) == sorted(other.files)

    @property
    def hash(self):
        """ Return hash, either from deserialization or local calculation. """
        if self._hash is UNSET:
            self._hash = self._calculate_hash()
        return self._hash

    @hash.deleter
    def hash(self):
        """ Reset the hash calculation.  Do this after modifying 'files'. """
        assert self.files, "Refusing to reset hash without 'files'"
        self._hash = UNSET

    def recalculate_hash(self) -> bool:
        """ Recalculate hash and indicate if hash has changed. """
        first_hash = self._hash
        assert first_hash is not UNSET, "Hash has not been calculated or provided"
        assert first_hash is not None, "Hash cannot be calculated"
        del self.hash
        return first_hash != self.hash

    def _calculate_hash(self) -> Optional[str]:
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
            parts.append(f"{f.hash} 0{f.mode:03o} {'/'.join(f.path.parts)}")
        parts.insert(0, self.name)
        payload = "\n".join(parts)
        h = hashlib.new(self.hash_algorithm)
        h.update(payload.encode("utf-8"))
        return h.hexdigest()

    def filter_files(self, filter: Callable[[AppManifestFile], bool]):
        """ Apply a filter function to :py:attr:`files` safely.

        Note that unlike the `filter_file` argument on :py:meth:`from_filesystem` and
        :py:meth:`from_tarball`, the :py:obj:`filter` function is given an entire
        :py:class:`AppManifestFile` object not just the file path.
        """
        if self._hash is UNSET:
            self.files = [f for f in self.files if filter(f)]
        else:
            raise TypeError("Inappropriate use of filter_files().  "
                            "This must be called before hash is calculated.")

    def drop_ds_autogen(self):
        """
        Remove place-holder files created by the deployment server from the manifest
        for the purpose of consistent hash creation.

        These files always live in ``local/app.conf`` and contain the literal
        text ``# Autogenerated file``.  Any other forms of this file are preserved.
        """
        local_app = PurePosixPath('local/app.conf')
        unwanted_hashs = {
            "a0c13b7008d9ef75d56be47cdb5ea3157f087bb7e773bd3d426a1998049e89b3"  # Nix - sha256
        }
        self.filter_files(lambda f: f.path != local_app or f.hash not in unwanted_hashs)

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
            "source": fspath(self.source),
            "hash_algorithm": self.hash_algorithm,
            "hash": self.hash,
            "files": [f.to_dict() for f in self.files]
        }
        return d

    @classmethod
    def from_archive(cls, archive: Path,
                     calculate_hash=True,
                     *,
                     filter_file: Optional[FileFilterFunction] = None) -> AppManifest:
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
            relpath = PurePosixPath(relpath)
            if filter_file is None or filter_file(relpath):
                f = AppManifestFile(relpath, gaf.mode, gaf.size, hash)
                manifest.files.append(f)
        if len(app_names) > 1:
            raise AppArchiveContentError("Found multiple top-level app names!  "
                                         f"Archive {archive} contains apps {', '.join(app_names)}")
        manifest.name = app_names.pop()
        return manifest

    @classmethod
    def from_filesystem(cls, path: Path,
                        name: Optional[str] = None,
                        follow_symlinks=False,
                        calculate_hash=True,
                        *,
                        filter_file: Optional[FileFilterFunction] = None) -> AppManifest:
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
                if filter_file is not None and not filter_file(rel_path):
                    continue
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
            if self._manifest.recalculate_hash():
                raise AppManifestStorageError("Manifest failed internal hash consistency test")
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
        with atomic_open(manifest_file, ".tmp", "w") as fp:
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
                           stored_file: Path,
                           *,
                           permanent_archive: Optional[Path] = None) -> StoredArchiveManifest:
        """
        Attempt to load an archive stored manifest from ``archive`` and ``stored_file`` paths.
        If the archive has changed since the manifest was stored, then an
        exception will be raised indicating the reason for invalidation.
        """
        # XXX: Optimization: tests if archive is newer than stored_file.  No need to open/parse JSON.
        if not stored_file.exists():
            raise AppManifestStorageInvalid("No stored manifest found")

        if permanent_archive is None:
            permanent_archive = archive

        try:
            stored = cls.read_json_manifest(stored_file)

            if stored.archive != permanent_archive:
                raise AppManifestStorageInvalid(f"Archive name differs: {stored.archive!r} != {permanent_archive!r}")
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
        manifest_file: Optional[Path] = None,
        *,
        read_manifest=True,
        write_manifest=True,
        permanent_archive: Optional[Path] = None,
        log_callback=print) -> AppManifest:
    """
    Load manifest for ``archive`` and create a stored copy of the manifest in
    ``manifest_file``.  On subsequent calls the manifest data stored to disk
    will be reused assuming ``manifest_file`` is up-to-date.

    File modification time and size are used to determine if ``archive`` has
    been changed since the ``manifest_file`` was written.

    If no ``manifest_file`` is provided, the default manifest naming convention
    will be applied where the ``manifest_file`` is stored in the same directory
    as ``archive``.

    If ``permanent_archive`` is provided, then we assume it is the persistent
    name and ``archive`` is a temporary resource.  In this mode, the default
    ``manifest_file`` is also based on ``permanent_archive`` not ``archive``.
    """
    archive = Path(archive)
    if permanent_archive:
        permanent_archive = Path(permanent_archive)
    manifest = None

    if manifest_file is None and (read_manifest or write_manifest):
        if permanent_archive is None:
            manifest_file = get_stored_manifest_name(archive)
        else:
            manifest_file = get_stored_manifest_name(permanent_archive)
    else:
        manifest_file = Path(manifest_file)

    if read_manifest and manifest_file.exists():
        try:
            sam = StoredArchiveManifest.from_json_manifest(archive, manifest_file,
                                                           permanent_archive=permanent_archive)
            manifest = sam.manifest
        except AppManifestStorageError as e:
            log_callback(f"Loading stored manifest failed:  {e}")

    if manifest is None:
        # log_callback(f"Calculating manifest for {archive} to be written to {manifest_file}")
        manifest = AppManifest.from_archive(archive)
        if permanent_archive:
            manifest.source = permanent_archive

        # Assume stored manifest have already undergone path checks, so existing
        # manifest are not rechecked.  As path checking is done before extraction,
        # where bad paths can actually cause damage, the check is is just a
        # precaution to promote early detection of malicious behavior.
        manifest.check_paths()

        if write_manifest:
            create_manifest_from_archive(archive, manifest_file, manifest)

    return manifest
