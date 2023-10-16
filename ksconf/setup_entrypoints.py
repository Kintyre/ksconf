""" Defines all command prompt entry points for CLI actions

This is a silly hack allows for fallback mechanism when
    (a) running unit tests (can happen before install)
    (b) unexpected issues with importlib.metadata or backport
"""

from __future__ import absolute_import, unicode_literals

from importlib import import_module
from typing import NamedTuple, Optional


class Ep(NamedTuple):
    name: str
    module_name: str
    object_name: Optional[str] = None

    @property
    def formatted(self):
        if self.object_name is None:
            return f"{self.name} = {self.module_name}"
        else:
            return f"{self.name} = {self.module_name}:{self.object_name}"


# autopep8: off
_entry_points = {
    "console_scripts": [
        Ep("ksconf", "ksconf.__main__", "cli"),
    ],
    # Custom end_point for ksconf subcommand registration
    "ksconf_cmd": [
        Ep("attr-get",      "ksconf.commands.attr",         "AttrGetCmd"),
        Ep("attr-set",      "ksconf.commands.attr",         "AttrSetCmd"),
        Ep("check",         "ksconf.commands.check",        "CheckCmd"),
        Ep("combine",       "ksconf.commands.combine",      "CombineCmd"),
        Ep("diff",          "ksconf.commands.diff",         "DiffCmd"),
        Ep("filter",        "ksconf.commands.filter",       "FilterCmd"),
        Ep("merge",         "ksconf.commands.merge",        "MergeCmd"),
        Ep("minimize",      "ksconf.commands.minimize",     "MinimizeCmd"),
        Ep("package",       "ksconf.commands.package",      "PackageCmd"),
        Ep("promote",       "ksconf.commands.promote",      "PromoteCmd"),
        Ep("rest-export",   "ksconf.commands.restexport",   "RestExportCmd"),
        Ep("rest-publish",  "ksconf.commands.restpublish",  "RestPublishCmd"),
        Ep("snapshot",      "ksconf.commands.snapshot",     "SnapshotCmd"),
        Ep("sort",          "ksconf.commands.sort",         "SortCmd"),
        Ep("unarchive",     "ksconf.commands.unarchive",    "UnarchiveCmd"),
        Ep("xml-format",    "ksconf.commands.xmlformat",    "XmlFormatCmd"),
    ],
    "ksconf_plugins": [
        Ep("internal_plugins", "ksconf.plugins._internal"),
    ],

}
# autopep8: on


def get_entrypoints_setup():
    """ Build entry point text descriptions for ksconf packaging """
    setup = {}
    for (group, entries) in _entry_points.items():
        setup[group] = [ep.formatted for ep in entries]
    return setup


class LocalEntryPoint:
    """ Bare minimum stand-in for entrypoints.EntryPoint """

    def __init__(self, data):
        self._data = data
        self.dist = None

    def __getattr__(self, attr):
        return getattr(self._data, attr)

    def load(self):
        mod = import_module(self.module_name)
        return getattr(mod, self.object_name)


def get_entrypoints_fallback(group):
    entry_points = {}
    for ep in _entry_points[group]:
        entry_points[ep.name] = LocalEntryPoint(ep)
    return entry_points


def debug():
    # For debugging internally defined entrypoints
    print("Builtin entrypoints:")
    for (group, entries) in _entry_points.items():
        print(f"[{group}]")
        for ep in entries:
            if ep.object_name:
                print(f"{ep.name:15} = {ep.module_name:30} : {ep.object_name}")
            else:
                print(f"{ep.name:15} = {ep.module_name:30}")
        print("")


if __name__ == '__main__':
    debug()
