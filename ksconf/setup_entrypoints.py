""" Defines all command prompt entry points for CLI actions

This is a silly hack that serves 2 purposes:

  (1) It works around and apparent Python 3.4/3.5 bug on Windows where [options.entry_point] in
      setup.cfg is ignored hence 'ksconf' isn't installed as a console script and custom ksconf_*
      entry points are not available.  (So no CLI commands are available)
  (2) It allows for fallback mechanism when
       (a) running unit tests (can happen before install)
       (b) if entrypoints or pkg_resources are not available at run time (Splunk's embedded python)
"""

from __future__ import absolute_import, unicode_literals
from collections import namedtuple, OrderedDict
from importlib import import_module

Ep = namedtuple("Ep", ("name", "module_name", "object_name")) #, "extras", "dist")


_entry_points = {
    "console_scripts" : [
        Ep("ksconf", "ksconf.__main__", "cli"),
    ],
    # Custom end_point for ksconf subcommand registration
    "ksconf_cmd" : [
        Ep("check",     "ksconf.commands.check",    "CheckCmd"),
        Ep("combine",   "ksconf.commands.combine",  "CombineCmd"),
        Ep("diff",      "ksconf.commands.diff",     "DiffCmd"),
        Ep("promote",   "ksconf.commands.promote",  "PromoteCmd"),
        Ep("merge",     "ksconf.commands.merge",    "MergeCmd"),
        Ep("minimize",  "ksconf.commands.minimize", "MinimizeCmd"),
        Ep("sort",      "ksconf.commands.sort",     "SortCmd"),
        Ep("unarchive", "ksconf.commands.unarchive","UnarchiveCmd"),
    ],
}


def get_entrypoints_setup():
    setup = {}
    for (group, entries) in _entry_points.items():
        setup[group] = [ "{0.name} = {0.module_name}:{0.object_name}".format(ep) for ep in entries ]
    return setup


class LocalEntryPoint(object):
    """ Bare minimum standin for entrypoints.EntryPoint """

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
