#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from ksconf.filter import FilteredListSplunkGlob


class KsconfUtilsTest(unittest.TestCase):

    def test_xarg_limit(self):
        from ksconf.util import _xargs
        results = list(_xargs(["%06x" % i for i in range(10000)]))
        self.assertGreater(len(results), 1)

    def test_splglob_simple(self):
        fl = FilteredListSplunkGlob(default=False)
        fl.feedall(["apple", "spoon", "hotdog", r"bak*"])
        self.assertTrue(fl.match("hotdog"))
        self.assertTrue(fl.match("bake"))
        self.assertFalse(fl.match("egg"))
        self.assertFalse(fl.match("theapplejack"))

    def test_splglob_wildcards(self):
        fl = FilteredListSplunkGlob()
        fl.feedall([
            "keep/me",
            ".../*.jpg",
            "....png",
            "prefix/*/suffix",
            "prefix2/.../suffix2",
            "prefix3/**/suffix3",
        ])

        self.assertTrue(fl.match("keep/me"))
        self.assertFalse(fl.match("nested/keep/me"))
        self.assertFalse(fl.match("keep/me/nope"))

        self.assertTrue(fl.match("/some/nested/pict.jpg"))
        self.assertTrue(fl.match("/very/ver/ve/v/nested/pict.jpg"))
        self.assertTrue(fl.match("/very/ver/ve/v/nested/pict.png"))

        self.assertFalse(fl.match("image.jpg"))  # Must have at least one '/'
        self.assertTrue(fl.match("image.png"))  # No prefix required

        # match() assumes that 'value' is normalized first
        self.assertFalse(fl.match("\\not\\supported\\pict.jpg"))
        self.assertTrue(fl.match("\\this\\is\\supported\\pict.png"))

        # Using match_path() handles dos->unix (*if running on Windows)
        if sys.platform.startswith("win"):
            self.assertTrue(fl.match_path("\\not\\supported\\pict.jpg"))

        self.assertTrue(fl.match("prefix/blah/suffix"))
        self.assertFalse(fl.match("prefix/b/l/a/h/suffix"))

        self.assertTrue(fl.match("prefix2/blah/suffix2"))
        self.assertTrue(fl.match("prefix2/b/l/a/h/suffix2"))
        self.assertFalse(fl.match("prefix2/suffix2"))

        self.assertTrue(fl.match("prefix3/blah/suffix3"))
        self.assertTrue(fl.match("prefix3/b/l/a/h/suffix3"))
        self.assertFalse(fl.match("prefix3/suffix3"))


class KsconfMiscIternalsTest(unittest.TestCase):

    def test_entrypoints_setup(self):
        from ksconf.setup_entrypoints import get_entrypoints_setup
        get_entrypoints_setup()

    def test_entrypoint_fallback(self):
        from ksconf.setup_entrypoints import get_entrypoints_fallback
        for ep in get_entrypoints_fallback("ksconf_cmd").values():
            ep.module_name
            ep.load()
            break

    def test_entrypoints(self):
        from ksconf.command import _get_fallback, get_entrypoints
        get_entrypoints("ksconf_cmd", "sort")

        # Just to exercise this (coverage and prevent regressions)
        _get_fallback("ksconf_cmd")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
