# -*- coding: utf-8 -*-
""" Splunk App helper classes

Note that these representations are for native Splunk apps that use 'default'
and 'local' and have not built-in concept of ksconf layers.

"""

from __future__ import absolute_import, annotations, unicode_literals

import hashlib
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from io import StringIO
from os import fspath
from pathlib import Path
from typing import ClassVar, Iterable, Tuple

from ksconf.archive import extract_archive, gaf_filter_name_like, sanity_checker
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import (PARSECONF_LOOSE, ConfType, conf_attr_boolean,
                                default_encoding, parse_conf)
from ksconf.consts import MANIFEST_HASH, UNSET
from ksconf.util.file import relwalk

if sys.version_info < (3, 8):
    from typing import List
else:
    List = list


class AppArchiveError(Exception):
    pass


class AppManifestContentError(Exception):
    pass


@dataclass
class AppInfo:
    """ Basic Splunk application info container.
    A majority of the info is extracted from ``app.conf``
    """
    name: str
    label: str = None
    id: str = None
    version: str = None
    author: str = None
    description: str = None
    state: str = None
    build: int = None

    is_configured: bool = field(init=False)
    allows_disable: bool = field(init=False)
    state_change_requires_restart: bool = field(init=False)

    install_source_checksum: str = field(init=False)
    install_source_local_checksum: str = field(init=False)
    check_for_updates: bool = field(init=False)
    is_visible: bool = field(init=False)

    deployer_lookups_push_mode: str = field(init=False)
    deployer_push_mode: str = field(init=False)

    _conf_translate_pairs: ClassVar[List[Tuple[str, List[str]]]] = [
        ("launcher", [
            "version",
            "author",
            "description"]),
        ("install", [
            "state",
            "build",
            "is_configured",
            "allows_disable",
            "install_source_checksum",
            "install_source_local_checksum",
            "state_change_requires_restart",
        ]),
        ("package", [
            "id",
            "check_for_updates"]),
        ("ui", [
            "label",
            "is_visible"]),
        ("shclustering", [
            "deployer_lookups_push_mode",
            "deployer_push_mode"]
         ),
    ]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_conf(cls, name, conf: ConfType) -> "AppInfo":
        """
        Create AppInfo from an app.conf configuration content.
        """
        new = cls(name)

        def convert_attr(attr_name, value):
            # XXX: Is there a better approach for dataclasses?  fields() returns a list
            data_type = cls.__annotations__.get(attr_name, None)
            convert_function = None
            if data_type == "bool":
                convert_function = conf_attr_boolean
            elif data_type == "int":
                convert_function = int
            else:
                return value
            try:
                return convert_function(value)
            except ValueError:
                # Best effort.  pass the buck to the consumer
                return value

        for stanza_name, attributes in cls._conf_translate_pairs:
            if stanza_name in conf:
                stanza = conf[stanza_name]
                for attr in attributes:
                    if attr in stanza:
                        setattr(new, attr, convert_attr(attr, stanza[attr]))
        return new

    @classmethod
    def from_app_dir(cls, app_path: Path) -> "AppInfo":
        """
        Create an AppInfo from a local file system.  This expects a standard
        (non-layered) installed or extracted app folder.  Both ``default`` and
        ``local`` are considered.
        """
        app_path = Path(app_path)
        app_conf_paths = [
            app_path / "default" / "app.conf",
            app_path / "local" / "app.conf"
        ]
        conf = {}
        for app_conf_path in app_conf_paths:
            if app_conf_path.is_file():
                conf = merge_conf_dicts(conf, parse_conf(app_conf_path, PARSECONF_LOOSE))
        return cls.from_conf(app_path.name, conf)

    @classmethod
    def from_archive(cls, archive: Path):
        ''' Returns list of app names, merged app_conf and a dictionary of extra facts that may be useful '''
        archive = Path(archive)

        app_names = set()
        app_confs = defaultdict(dict)

        is_app_conf = gaf_filter_name_like("app.conf")
        for gaf in sanity_checker(extract_archive(archive,
                                                  extract_filter=is_app_conf)):
            app_name, relpath = gaf.path.split("/", 1)
            if relpath.endswith("/app.conf") and gaf.payload:
                conf_folder = relpath.rsplit("/")[0]
                tmp = StringIO(gaf.payload.decode(default_encoding))
                tmp.name = fspath(archive.joinpath(gaf.path))
                app_confs[conf_folder] = parse_conf(tmp, profile=PARSECONF_LOOSE)
                del tmp
            app_names.add(app_name)
            del app_name, relpath

        if len(app_names) > 1:
            raise AppArchiveError("Found multiple top-level app names!  "
                                  f"Archive {archive} contains apps {', '.join(app_names)}")

        # Merge default and local (in the correct order)
        conf = merge_conf_dicts(app_confs["default"], app_confs["local"])
        app_name = app_names.pop()
        return cls.from_conf(app_name, conf)


@dataclass(order=True)
class AppManifestFile:
    path: Path
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
    def from_dict(cls, data: dict) -> "AppManifestFile":
        return cls(Path(data["path"]), data["mode"], data["size"], data["hash"])


@dataclass
class AppManifest:
    name: str = None
    hash_algorithm: str = field(default=MANIFEST_HASH)
    _hash: str = field(default=UNSET, init=False)
    files: List[AppManifestFile] = field(default_factory=list)

    def __eq__(self, other: AppManifest) -> bool:
        if self.name != other.name or self.hash != other.hash:
            return False
        return sorted(self.files) == sorted(other.files)

    @property
    def hash(self):
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
            # If OS issues, use:   {'/'.join(f.path.parts)}
            parts.append(f"{f.hash} 0{f.mode:o} {f.path}")
        parts.insert(0, self.name)
        payload = "\n".join(parts)
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
            "files": [f.to_dict() for f in self.files]
        }
        return d

    @classmethod
    def from_archive(cls, archive: Path,
                     calculate_hash=True) -> "AppManifest":
        """
        Create as new AppManifest from a tarball.  Set ``calculate_hash`` as
        False when only a file listing is needed.
        """
        manifest = cls()
        app_names = set()
        archive = Path(archive)

        if calculate_hash:
            h_ = hashlib.new(cls.hash_algorithm)

            def gethash(content):
                # h = hashlib.new(MANIFEST_HASH)
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
            f = AppManifestFile(Path(relpath), gaf.mode, gaf.size, hash)
            manifest.files.append(f)
        if len(app_names) > 1:
            raise AppManifestContentError("Found multiple top-level app names!  "
                                          f"Archive {archive} contains apps {', '.join(app_names)}")
        manifest.name = app_names.pop()
        return manifest

    @classmethod
    def from_filesystem(cls, path: Path,
                        name: str = None,
                        follow_symlinks=False,
                        calculate_hash=True) -> "AppManifest":
        """
        Create as new AppManifest from an existing directory structure.
        Set ``calculate_hash`` as False when only a file listing is needed.
        """
        path = Path(path)
        if name is None:
            name = path.name
        manifest = cls(name)
        h_ = hashlib.new(cls.hash_algorithm)

        for (root, _, files) in relwalk(path, followlinks=follow_symlinks):
            root_path = Path(root)
            for file_name in files:
                rel_path: Path = root_path.joinpath(file_name)
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


def get_info_manifest_from_archive(archive: Path,
                                   calculate_hash=True
                                   ) -> Tuple[AppInfo, AppManifest]:
    """ Get both AppInfo and AppManifest from a single archive.
    If ``calculate_hash`` is True, then the manifest will contain checksums for
    all files in the archive.  Without this, it's not possible to calculate a
    hash for the combined manifest.

    Use this function to collect both sets of information at once.
    """
    # XXX: Optimize to create AppInfo and AppManifest concurrently; from a single read of the archive.
    # XXX: Use this in ksconf.commands.unarchive
    archive = Path(archive)

    info = AppInfo.from_archive(archive)
    manifest = AppManifest.from_archive(archive, calculate_hash=calculate_hash)

    return info, manifest
