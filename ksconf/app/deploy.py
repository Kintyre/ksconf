# -*- coding: utf-8 -*-
"""
"""

from __future__ import absolute_import, annotations, unicode_literals

from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from os import fspath
from pathlib import Path, PurePath, PurePosixPath
from typing import Set

from ksconf.app import AppManifest
from ksconf.archive import extract_archive
from ksconf.compat import List
from ksconf.util.compare import cmp_sets

# Deployment Action classes


class DeployActionType(Enum):
    SET_APP_NAME = "app"
    SOURCE_REFERENCE = "source"
    EXTRACT_FILE = "extract_file"
    REMOVE_FILE = "remove"

    """ Implement in future phase
    SET_SYMLINK = "link"
    UPDATE_META = "meta"
    """

    def __str__(self):
        return self.value


# Specific action definitions

@dataclass
class DeployAction:
    # Abstract base class
    action: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["action"] = str(self.action)

        for dc_field in fields(self):
            if dc_field.name == "action":
                continue

            value = data[dc_field.name]
            t = eval(dc_field.type)
            if issubclass(t, PurePath):
                value = fspath(value)
                data[dc_field.name] = value
        return data

    @classmethod
    def from_dict(self, data: dict) -> DeployAction:
        data = data.copy()
        action = data.pop("action")
        action = DeployActionType(action)
        da_class = get_deploy_action_class(action)
        for dc_field in fields(da_class):
            if dc_field.name == "action":
                continue
            value = data[dc_field.name]
            t = eval(dc_field.type)
            if issubclass(t, PurePath):
                value = t(value)
                data[dc_field.name] = value
        return da_class(**data)


@dataclass
class DeployAction_ExtractFile(DeployAction):
    action: str = field(init=False, default=DeployActionType.EXTRACT_FILE)
    subtype: str
    path: PurePosixPath
    mode: int = None
    mtime: int = None
    hash: str = None
    rel_path: str = None


@dataclass
class DeployAction_RemoveFile(DeployAction):
    action: str = field(init=False, default=DeployActionType.REMOVE_FILE)
    path: PurePosixPath


@dataclass
class DeployAction_SetAppName(DeployAction):
    action: str = field(init=False, default=DeployActionType.SET_APP_NAME)
    name: str


@dataclass
class DeployAction_SourceReference(DeployAction):
    action: str = field(init=False, default=DeployActionType.SOURCE_REFERENCE)
    archive_path: str
    hash: str


def get_deploy_action_class(action: str) -> DeployAction:
    return {
        DeployActionType.EXTRACT_FILE: DeployAction_ExtractFile,
        DeployActionType.REMOVE_FILE: DeployAction_RemoveFile,
        DeployActionType.SET_APP_NAME: DeployAction_SetAppName,
        DeployActionType.SOURCE_REFERENCE: DeployAction_SourceReference,
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

    def to_dict(self) -> dict:
        d = {
            "actions": [a.to_dict() for a in self.actions]
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> DeploySequence:
        seq = cls()
        for action in data["actions"]:
            da = DeployAction.from_dict(action)
            seq.add(da)
        return seq

    @classmethod
    def from_manifest(
            cls,
            manifest: AppManifest) -> DeploySequence:
        """
        Fresh deploy of an app from scratch.

        (There should probably be a new
        op-code for this, eventually instead of listing every single file.)
        """
        dc = cls()
        dc.add(DeployAction_SourceReference(manifest.source, manifest.hash))
        dc.add(DeployAction_SetAppName(manifest.name))
        for f in manifest.files:
            dc.add(DeployActionType.EXTRACT_FILE, "create", f.path, mode=f.mode, hash=f.hash)
        return dc

    @classmethod
    def from_manifest_transformation(
            cls,
            base: AppManifest,
            target: AppManifest) -> DeploySequence:
        seq = cls()
        if base is None:
            return cls.from_manifest(target)
        if base.name != target.name:
            raise ValueError(f"Manifest must have the same app name.  {base.name} != {target.name}")
        seq.add(DeployAction_SourceReference(target.source, target.hash))
        seq.add(DeployAction_SetAppName(target.name))

        base_files = {f.path: f for f in base.files}
        target_files = {f.path: f for f in target.files}

        base_only, common, target_only = cmp_sets(base_files, target_files)

        for fn in target_only:
            f = target_files[fn]
            seq.add(DeployAction_ExtractFile("create", fn, mode=f.mode, hash=f.hash))

        for fn in common:
            base_file = base_files[fn]
            target_file = target_files[fn]
            if base_file != target_file:
                sub = "attr" if base_file.content_match(target_file) else "update"
                seq.add(DeployAction_ExtractFile(sub, fn, target_file.mode, hash=target_file.hash))

        for fn in base_only:
            seq.add(DeployAction_RemoveFile(fn))

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

    def resolve_source(self, source, hash):
        # In the future, this may look in a local/remote directory based on the hash value.
        return Path(source)

    def apply_sequence(self, deployment_sequence: DeploySequence):
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
            elif isinstance(action, DeployAction_SourceReference):
                archive = self.resolve_source(action.archive_path, action.hash)
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
            if full_path.is_file():
                full_path.unlink()

        # Cleanup any empty directories (longest paths first)
        for d in sorted(set(f.parent for f in remove_path),
                        key=_path_by_part_len,
                        reverse=True):
            full_path = self.dest.joinpath(d)
            if full_path.is_dir() and full_path.stat().st_nlink == 2:
                # print(f"Cleaning empty directory {d}")
                try:
                    full_path.rmdir()
                except OSError:
                    pass


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
        dest_dir.mkdir(dir_mode, parents=True, exist_ok=True)

    # Expand matching files
    for gaf in extract_archive(archive):
        p = Path(gaf.path)
        if p in keep_paths:
            dest_path: Path = dest.joinpath(p)
            dest_path.write_bytes(gaf.payload)
            dest_path.chmod(gaf.mode)
    # Anything else?
