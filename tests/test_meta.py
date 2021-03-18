#!/usr/bin/env python

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from io import open

# Allow interactive execution from CLI,  cd tests; ./test_meta.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.conf.delta import DIFF_OP_EQUAL, compare_cfgs
from ksconf.conf.meta import MetaData
from ksconf.conf.parser import parse_conf
from tests.cli_helper import TestWorkDir


class MetaDataTestCase(unittest.TestCase):

    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        # Cleanup test working directory
        self.twd.clean()

    @property
    def sample01(self):
        return self.twd.write_file("metadata/default.meta", """\
        []
        access = read : [ * ], write : [ admin, power ]
        export = system
        modtime = 1517931832.143147000
        version = 6.2.1

        [macros]
        export = system
        owner = kintyrela
        version = 7.0.0

        [macros/edit_timerange]
        export = none
        modtime = 1518812678.293270000
        owner = admin
        version = 7.0.1

        [props/Vendor%3AEngine%3AErrors]
        access = read : [ * ], write : [ admin ]
        modtime = 1518754379.345177000
        owner = joeadmin
        version = 6.3.5

        [props/Vendor%3AEngine%3AErrors/EXTRACT-VendorId]
        access = read : [ * ], write : [ admin ]
        modtime = 1518721483.877502000
        owner = admin
        version = 7.0.1
        """)

    def test_simple_all_levels(self):
        md = MetaData()
        md.feed_file(self.sample01)

        d = md.get("macros")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"], "kintyrela")

        glob = md.get()
        props = md.get("props")
        self.assertEqual(glob, props, "Expect [props] (undefined) to be identical to []")

        d = md.get("props", "Vendor:Engine:Errors")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"], "joeadmin")

        d = md.get("props", "Vendor:Engine:Errors", "EXTRACT-VendorId")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"], "admin")
        self.assertEqual(d["modtime"], "1518721483.877502000")

    def test_encoded_slash(self):
        """ Ensure that encoded slashes (%2f) are parsed correctly. """
        f = self.twd.write_file("metadata/default.meta", """\
        []
        export = system
        owner = nobody

        [props/silly%2Fname/EXTRACT-other]
        modtime = 1518784292
        """)
        md = MetaData()
        md.feed_file(f)

        self.assertEqual(md.get()["owner"], "nobody")
        self.assertEqual(
            md.get("props", "silly/name", "EXTRACT-other")["modtime"],
            "1518784292")

    def test_write_with_compare(self):
        orig = self.sample01
        new = self.twd.get_path("metadata/local.meta")
        md = MetaData()
        md.feed_file(orig)
        with open(new, "w", encoding="utf-8") as stream:
            md.write_stream(stream)

        a = parse_conf(orig)
        b = parse_conf(new)
        diffs = compare_cfgs(a, b)

        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].tag, DIFF_OP_EQUAL)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
