""" Splunk Application facts:

Easily collect Splunk app name, version, label, and other nuggets from ``app.conf``

"""

from __future__ import absolute_import, annotations, unicode_literals

from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from io import StringIO
from os import fspath
from pathlib import Path
from typing import ClassVar

from ksconf.app.manifest import AppArchiveContentError
from ksconf.archive import extract_archive, gaf_filter_name_like
from ksconf.compat import List, Tuple
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import (PARSECONF_LOOSE, ConfType, conf_attr_boolean,
                                default_encoding, parse_conf)


@dataclass
class AppFacts:
    """ Basic Splunk application info container.
    A majority of these facts are extracted from ``app.conf``
    """
    name: str
    label: str = None
    id: str = None
    version: str = None
    author: str = None
    description: str = None
    state: str = None
    build: int = None

    is_configured: bool = field(init=False, default=None)
    allows_disable: bool = field(init=False, default=None)
    state_change_requires_restart: bool = field(init=False, default=None)

    install_source_checksum: str = field(init=False, default=None)
    install_source_local_checksum: str = field(init=False, default=None)
    check_for_updates: bool = field(init=False, default=None)
    is_visible: bool = field(init=False, default=None)

    deployer_lookups_push_mode: str = field(init=False, default=None)
    deployer_push_mode: str = field(init=False, default=None)

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

    def to_tiny_dict(self, *keep_attrs) -> dict:
        """ Return dict representation, discarding the Nones """
        return {k: v for k, v in asdict(self).items() if v is not None or k in keep_attrs}

    @classmethod
    def from_conf(cls, name, conf: ConfType) -> AppFacts:
        """
        Create AppFacts from an app.conf configuration content.
        """
        new = cls(name)

        type_mapping = {f.name: f.type for f in fields(cls) if f.type in ("bool", "int")}

        def convert_attr(attr_name, value):
            # XXX: Is there a better approach for dataclasses?  fields() returns a list
            data_type = type_mapping.get(attr_name, None)
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
    def from_app_dir(cls, app_path: Path) -> AppFacts:
        """
        Create an AppFacts from a local file system.  This expects a standard
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
        for gaf in extract_archive(archive, extract_filter=is_app_conf):
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
            raise AppArchiveContentError(
                f"Found multiple top-level app names!  Archive {archive} "
                f"contains apps {', '.join(app_names)}")

        # Merge default and local (in the correct order)
        conf = merge_conf_dicts(app_confs["default"], app_confs["local"])
        app_name = app_names.pop()
        return cls.from_conf(app_name, conf)
