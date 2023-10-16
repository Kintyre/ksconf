""" Splunk Application facts:

Easily collect Splunk app name, version, label, and other nuggets from ``app.conf``

"""

from __future__ import absolute_import, annotations, unicode_literals

from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from os import fspath
from pathlib import Path
from typing import Any, ClassVar, Optional

from ksconf.app.manifest import AppArchiveContentError
from ksconf.archive import extract_archive, gaf_filter_name_like
from ksconf.compat import Dict, List, Set, Tuple
from ksconf.conf.merge import merge_conf_dicts
from ksconf.conf.parser import (PARSECONF_LOOSE, ConfType, conf_attr_boolean,
                                default_encoding, parse_conf, parse_string)

OInt = Optional[int]
OStr = Optional[str]
OBool = Optional[bool]


@dataclass
class AppFacts:
    """ Basic Splunk application info container.
    A majority of these facts are extracted from ``app.conf``
    """
    name: str

    label: OStr = None
    id: OStr = None
    version: OStr = None
    author: OStr = None
    description: OStr = None
    state: OStr = None
    build: OStr = None

    is_configured: OBool = field(init=False, default=None)
    allows_disable: OBool = field(init=False, default=None)
    state_change_requires_restart: OBool = field(init=False, default=None)

    install_source_checksum: OStr = field(init=False, default=None)
    install_source_local_checksum: OStr = field(init=False, default=None)
    check_for_updates: OBool = field(init=False, default=None)
    is_visible: OBool = field(init=False, default=None)

    deployer_lookups_push_mode: OStr = field(init=False, default=None)
    deployer_push_mode: OStr = field(init=False, default=None)

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

    def to_tiny_dict(self, *keep_attrs: str) -> Dict[str, Any]:
        """ Return dict representation, discarding the Nones """
        return {k: v for k, v in asdict(self).items() if v is not None or k in keep_attrs}

    @classmethod
    def from_conf(cls, name: str, conf: ConfType) -> AppFacts:
        """
        Create AppFacts from an app.conf configuration content.
        """
        new = cls(name)

        # Another possible option:
        # typing.get_type_hints(ksconf.app.facts.AppFacts)["build"].__args__[0]      (__args__[0] due to Optional)
        type_mapping = {f.name: f.type for f in fields(cls) if f.type in ("OBool", "OInt")}

        def convert_attr(attr_name, value):
            # XXX: Is there a better approach for dataclasses?  fields() returns a list
            data_type = type_mapping.get(attr_name, None)
            convert_function = None
            if data_type == "OBool":
                convert_function = conf_attr_boolean
            elif data_type == "OInt":
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

        app_names: Set[str] = set()
        app_confs: Dict[str, str] = defaultdict(dict)

        is_app_conf = gaf_filter_name_like("app.conf")
        for gaf in extract_archive(archive, extract_filter=is_app_conf):
            app_name, relpath = gaf.path.split("/", 1)
            if relpath.endswith("/app.conf") and gaf.payload:
                conf_folder = relpath.rsplit("/")[0]
                app_confs[conf_folder] = parse_string(gaf.payload.decode(default_encoding),
                                                      name=fspath(archive.joinpath(gaf.path)),
                                                      profile=PARSECONF_LOOSE)
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
