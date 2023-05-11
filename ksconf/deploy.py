# -*- coding: utf-8 -*-
"""
"""

from __future__ import absolute_import, annotations, unicode_literals

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from os import fspath
from pathlib import Path
from typing import Any, ClassVar, Dict, Set, Type

from ksconf.app import AppManifest
from ksconf.archive import extract_archive
from ksconf.consts import MANIFEST_HASH
from ksconf.util.compare import cmp_sets
from ksconf.util.file import file_hash

if sys.version_info < (3, 8):
    from typing import List
else:
    List = list


class AppManifestStorageError(Exception):
    pass


class AppManifestStorageInvalid(AppManifestStorageError):
    pass


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
    def from_json_manifest(cls,
                           archive: Path,
                           stored_file: Path) -> "StoredArchiveManifest":
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


def create_manifest_from_archive(archive_file: Path,
                                 manifest_file: Path,
                                 manifest: AppManifest):
    sam = StoredArchiveManifest.from_file(archive_file, manifest)
    sam.write_json_manifest(manifest_file)
    return sam


def get_stored_manifest_name(archive: Path):
    """ Calculate the name of the stored manifest file based on ``archive``. """
    c = archive.with_name(f".{archive.name}.manifest")
    return c


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
        print(f"Calculating manifest for {archive}")
        manifest = AppManifest.from_archive(archive)

        if write_manifest:
            create_manifest_from_archive(archive, manifest_file, manifest)

    return manifest


# Instead of just extracting only, I think we need a function that extracts (adds/updates),
# changes attribute (mode), and removes old files.
# Adding rewrites would be nice, but probably *only* useful for the 'unarchive' command.


class DeployActionType(Enum):
    SET_APP_NAME = "app"
    EXTRACT_FILE = "extract_file"
    REMOVE_FILE = "remove"

    """ Implement in future phase
    SET_SYMLINK = "link"
    UPDATE_META = "meta"
    """

    def __str__(self):
        return self.value


@dataclass
class DeployAction:
    action: str


@dataclass
class DeployAction_ExtractFile(DeployAction):
    action: str = field(init=False, default=DeployActionType.EXTRACT_FILE)
    path: Path
    mode: int = None
    mtime: int = None
    hash: str = None
    rel_path: str = None


@dataclass
class DeployAction_SetAppName(DeployAction):
    action: str = field(init=False, default=DeployActionType.SET_APP_NAME)
    name: str


@dataclass
class DeployAction_RemoveFile(DeployAction):
    action: str = field(init=False, default=DeployActionType.REMOVE_FILE)
    path: Path = None


def get_deploy_action_class(action: str) -> DeployAction:
    return {
        DeployActionType.EXTRACT_FILE: DeployAction_ExtractFile,
        DeployActionType.REMOVE_FILE: DeployAction_RemoveFile,
        DeployActionType.SET_APP_NAME: DeployAction_SetAppName,
    }[action]


'''
@dataclass
class DeployIntention:
    """ Container describing a deployment transformation intention. """
    path: Path
    action: DeployIntentionActions
    detail: Any = None

    _detail_class_mapping: ClassVar = {
        DeployIntentionActions.EXTRACT_FILE: _DeployAction_Extract,
        DeployIntentionActions.SET_APP_NAME: _DeployAction_SetAppName,
    }

    def __post_init__(self):
        detail_cls = self._detail_class_mapping.get(self.action)
        if detail_cls:
            if isinstance(self.detail, dict) and self.detail:
                self.detail = detail_cls(**self.detail)
        self.detail = detail_cls()
'''


class DeploySequence:
    def __init__(self):
        self.actions: List[DeployAction] = []
        self.actions_by_type = Counter()

    def add(self, action: str, *args, **kwargs):
        if not isinstance(action, DeployAction):
            action_cls = get_deploy_action_class(action)
            action = action_cls(*args, **kwargs)
        else:
            assert not args and not kwargs
        self.actions_by_type[action.action] += 1
        self.actions.append(action)

    @classmethod
    def from_manifest(
            cls,
            manifest: AppManifest) -> "DeploySequence":
        dc = cls()
        dc.add(DeployAction_SetAppName(manifest.name))
        for f in manifest.files:
            dc.add(DeployActionType.EXTRACT_FILE, f.path, mode=f.mode, hash=f.hash)
        return dc

    @classmethod
    def from_manifest_transformation(cls,
                                     base: AppManifest,
                                     target: AppManifest) -> "DeploySequence":
        seq = cls()
        if base.name != target.name:
            raise ValueError(f"Manifest must have the same app name.  {base.name} != {target.name}")
        seq.add(DeployAction_SetAppName(target.name))

        base_files = {f.path: f for f in base.files}
        target_files = {f.path: f for f in target.files}

        base_only, common, target_only = cmp_sets(base_files, target_files)

        for fn in target_only:
            f = target_files[fn]
            seq.add(DeployAction_ExtractFile(fn, mode=f.mode, hash=f.hash))
            # seq.add(DeployAction_RemoveFile(fn))

        for fn in common:
            base_file = base_files[fn]
            target_file = target_files[fn]
            if base_file != target_file:
                seq.add(DeployAction_ExtractFile(fn, target_file.mode, hash=target_file.hash, rel_path="FILE UPDATED"))

        for fn in base_only:
            seq.add(DeployAction_RemoveFile(fn))
            # f = base_files[fn]
            # seq.add(DeployAction_ExtractFile(fn, mode=f.mode, hash=f.hash))

        return seq


# Will we need this, or can we get all this as class methods within DeploySequence?
class DeployPlanner():
    pass


def _path_by_part_len(path: Path):
    # sort helper function for directory top-down/bottom-up operations
    return len(path.parts), path


class DeployApply:
    def __init__(self, dest: Path):
        self.dest = dest
        self.dir_mode = 0o770

    def apply_sequence(self,
                       archive: Path,
                       deployment_sequence: DeploySequence):
        '''
        Apply a pre-calculated deployment sequence to the local file system.
        '''
        #
        '''
        app = None
        items = []
        for action in deployment_sequence.actions:
            if action.action == DeployActionType.SET_APP_NAME:
                if items:
                    self.apply_sequence_for_app(archive, deployment_sequence)
                app = action.name
        '''

        '''
    def apply_sequence_for_app(self,
            archive: Path,
            app_name: str,
            deployment_sequence: DeploySequence):
        '''
        keep_paths: Set[Path] = set()
        make_dirs: Set[Path] = set()
        remove_path: Set[Path] = set()
        app_path = Path()
        for action in deployment_sequence.actions:
            if isinstance(action, DeployAction_ExtractFile):
                path = app_path.joinpath(action.path)
                keep_paths.add(path)
                make_dirs.add(path.parent)
            elif isinstance(action, DeployAction_SetAppName):
                app_path = Path(action.name)
            elif isinstance(action, DeployAction_RemoveFile):
                remove_path.add(app_path.joinpath(action.path))
            else:
                raise TypeError(f"Unable to handle action of type {type(action)}")

        # Make necessary directories
        for d in sorted(make_dirs, key=_path_by_part_len):
            dest_dir: Path = self.dest.joinpath(d)
            # Even with careful sorting, we must still use parents=True as some
            # directories contain no files, such as 'ui' in 'default/data/ui/nav'.
            dest_dir.mkdir(self.dir_mode, parents=True, exist_ok=True)

        # Expand matching files
        for gaf in extract_archive(archive):
            p = Path(gaf.path)
            if p in keep_paths:
                dest_path: Path = self.dest.joinpath(p)
                dest_path.write_bytes(gaf.payload)
                # Should we use the chmod from the archive, or the one from the deployment sequence object?
                dest_path.chmod(gaf.mode)

        # Cleanup removed files
        for p in remove_path:
            full_path: Path = self.dest.joinpath(p)
            full_path.unlink()

        # Cleanup any empty directories (longest paths first)
        for d in sorted(set(f.parent for f in remove_path),
                        key=_path_by_part_len,
                        reverse=True):
            full_path = self.dest.joinpath(d)
            if full_path.stat().st_nlink == 2:
                print(f"Cleaning empty directory {d}")
                full_path.rmdir()


def expand_archive_by_manifest(
        archive: Path,
        dest: Path,
        manifest: AppManifest,
        dir_mode=0o770):
    """
    Expand an tarball to a local file system including only the files referenced
    by the files within the app manifest.

    This function assumes that safety checks on manifest have already been
    performed, such as eliminating any absolute paths.
    """
    # XXX: Optimize out inefficiencies created by our use of extract_archive()

    ''' If no ``manifest`` is provided, all files are expanded.
    Not sure we want to allow this.  Let's keep this disabled unless needed.
    if manifest is None:
        # It's assumed that this is non-normal code path; as this is inefficient
        manifest = AppManifest.from_archive(archive, calculate_hash=False)
    '''
    keep_paths = set()
    make_dirs = set()
    app_path = Path(manifest.name)
    for f in manifest.files:
        path = app_path.joinpath(f.path)
        keep_paths.add(path)
        make_dirs.add(path.parent)

    # Ensure shorter paths are created first
    make_dirs = [(len(d.parts), d) for d in make_dirs]

    # Make necessary directories
    for _, d in sorted(make_dirs):
        dest_dir: Path = dest.joinpath(d)
        dest_dir.mkdir(dir_mode, exist_ok=True)

    # Expand matching files
    for gaf in extract_archive(archive):
        p = Path(gaf.path)
        if p in keep_paths:
            dest_path: Path = dest.joinpath(p)
            dest_path.write_bytes(gaf.payload)
            dest_path.chmod(gaf.mode)
    # Anything else?
