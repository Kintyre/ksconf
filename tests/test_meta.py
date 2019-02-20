from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.conf.meta import MetaData
from tests.cli_helper import TestWorkDir



class MetaDataTestCase(unittest.TestCase):

    def test_simple_all_levels(self):
        twd = TestWorkDir()
        f = twd.write_file("metadata/default.meta", """\
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

        md = MetaData()
        md.feed(f)

        d = md.get_combined("macros")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"], "kintyrela")

        glob = md.get_combined()
        props = md.get_combined("props")
        self.assertEqual(glob, props, "Expect [props] (undefined) to be identical to []")

        d = md.get_combined("props", "Vendor:Engine:Errors")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"],  "joeadmin")

        d = md.get_combined("props", "Vendor:Engine:Errors", "EXTRACT-VendorId")
        self.assertEqual(d["export"], "system")
        self.assertEqual(d["owner"],  "admin")
        self.assertEqual(d["modtime"], "1518721483.877502000")

    def test_encoded_slash(self):
        """ Ensure that encoded slashes (%2f) are parsed correctly. """
        twd = TestWorkDir()
        f = twd.write_file("metadata/default.meta", """\
        []
        export = system
        owner = nobody

        [props/silly%2Fname/EXTRACT-other]
        modtime = 1518784292
        """)
        md = MetaData()
        md.feed(f)

        self.assertEqual(md.get_combined()["owner"], "nobody")
        self.assertEqual(
            md.get_combined("props", "silly/name", "EXTRACT-other")["modtime"],
            "1518784292")



if __name__ == '__main__':  # pragma: no cover
    unittest.main()
