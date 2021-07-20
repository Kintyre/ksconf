#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest


class KsconfUtilsTest(unittest.TestCase):

    def test_xarg_limit(self):
        from ksconf.util import _xargs
        results = list(_xargs(["%06x" % i for i in range(10000)]))
        self.assertGreater(len(results), 1)

    def test_bwlist(self):
        from ksconf.util.file import match_bwlist
        bwlist = ["apple", "spoon", "hotdog", r"bak*"]
        self.assertTrue(match_bwlist("hotdog", bwlist))
        self.assertTrue(match_bwlist("bake", bwlist))
        self.assertFalse(match_bwlist("egg", bwlist))
        self.assertFalse(match_bwlist("theapplejack", bwlist))

    def test_handle_p3koa(self):
        from ksconf.util import handle_py3_kw_only_args
        kw = {"a": 1, "b": 2}
        a, b, c = handle_py3_kw_only_args(kw, ("a", None), ("b", 3), ("c", 99))
        self.assertEqual(a, 1)
        self.assertEqual(b, 2)
        self.assertEqual(c, 99)

        # Should raise 'unexpected argument' here because 'a' is not defined
        kw = {a: 1}
        with self.assertRaises(TypeError):
            (c,) = handle_py3_kw_only_args(kw, ("c", 99))


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
        from ksconf.commands import _get_fallback, get_entrypoints
        get_entrypoints("ksconf_cmd", "sort")

        # Just to exercise this (coverage and prevent regressions)
        _get_fallback("ksconf_cmd")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
