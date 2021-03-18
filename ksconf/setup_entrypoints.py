""" Defines all command prompt entry points for CLI actions

This is a silly hack that serves 2 purposes:

  (1) It works around an apparent Python 3.4/3.5 bug on Windows where [options.entry_point] in
      setup.cfg is ignored hence 'ksconf' isn't installed as a console script and custom ksconf_*
      entry points are not available.  (So no CLI commands are available)
  (2) It allows for fallback mechanism when
       (a) running unit tests (can happen before install)
       (b) if entrypoints or pkg_resources are not available at run time (Splunk's embedded python)
"""

from __future__ import absolute_import, unicode_literals

from collections import OrderedDict, namedtuple
from importlib import import_module

Ep = namedtuple("Ep", ("name", "module_name", "object_name"))  # , "extras", "dist")


# autopep8: off
_entry_points = {
    "console_scripts": [
        Ep("ksconf", "ksconf.__main__", "cli"),
    ],
    # Custom end_point for ksconf subcommand registration
    "ksconf_cmd": [
        Ep("check",         "ksconf.commands.check",        "CheckCmd"),
        Ep("combine",       "ksconf.commands.combine",      "CombineCmd"),
        Ep("diff",          "ksconf.commands.diff",         "DiffCmd"),
        Ep("package",       "ksconf.commands.package",      "PackageCmd"),
        Ep("filter",        "ksconf.commands.filter",       "FilterCmd"),
        Ep("promote",       "ksconf.commands.promote",      "PromoteCmd"),
        Ep("merge",         "ksconf.commands.merge",        "MergeCmd"),
        Ep("minimize",      "ksconf.commands.minimize",     "MinimizeCmd"),
        Ep("snapshot",      "ksconf.commands.snapshot",     "SnapshotCmd"),
        Ep("sort",          "ksconf.commands.sort",         "SortCmd"),
        Ep("rest-export",   "ksconf.commands.restexport",   "RestExportCmd"),
        Ep("rest-publish",  "ksconf.commands.restpublish",  "RestPublishCmd"),
        Ep("unarchive",     "ksconf.commands.unarchive",    "UnarchiveCmd"),
        Ep("xml-format",    "ksconf.commands.xmlformat",    "XmlFormatCmd"),
    ],
}
# autopep8: on


def get_entrypoints_setup():
    setup = {}
    for (group, entries) in _entry_points.items():
        setup[group] = ["{0.name} = {0.module_name}:{0.object_name}".format(ep) for ep in entries]
    return setup


class LocalEntryPoint(object):
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
    entry_points = OrderedDict()
    for ep in _entry_points[group]:
        entry_points[ep.name] = LocalEntryPoint(ep)
    return entry_points


def debug():
    # For debugging internally defined entrypoints
    print("Builtin entrypoints:")
    for (group, entries) in _entry_points.items():
        print("[group]")
        for ep in entries:
            print("{0.name:15} = {0.module_name:30} : {0.object_name}".format(ep))
        print("")


if __name__ == '__main__':
    debug()
