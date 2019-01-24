#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *


class CliRestExportTest(unittest.TestCase):
    transforms_sample1 = """
    [single_quote_kv]
    REGEX = ([^=\s]+)='([^']+)'
    FORMAT = $1::$2
    MV_ADD = 0
    """

    def test_simple_transforms_insert(self):
        twd = TestWorkDir()
        f = twd.write_file("transforms.conf", self.transforms_sample1)
        with ksconf_cli:
            ko = ksconf_cli("rest-export", f)
            # XXX:  Check for more things...
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"([\r\n]+|^)curl -k")
            # Should use 'name' for stanza, and not be embedded in URL
            self.assertRegex(ko.stdout, r"name=single_quote_kv")
            # Make sure fancy regex is encoded as expected
            self.assertIn("%5B%5E%3D%5Cs%5D%2B", ko.stdout)
            self.assertNotRegex(ko.stdout, r"https://[^ ]+/single_quote_kv ")

    def test_simple_transforms_update(self):
        twd = TestWorkDir()
        f = twd.write_file("transforms.conf", self.transforms_sample1)
        with ksconf_cli:
            ko = ksconf_cli("rest-export", "--update", f)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"([\r\n]+|^)curl ")
            self.assertRegex(ko.stdout, r"https://[^ ]+/single_quote_kv ")
            self.assertNotRegex(ko.stdout, r"name=single_quote_kv")

    def test_warn_on_global_entry(self):
        twd = TestWorkDir()
        f = twd.write_file("props.conf", """
        EVAL-always_present = 1
        [syslog]
        REPORT-single-quote = single_quote_kv
        """)
        with ksconf_cli:
            ko = ksconf_cli("rest-export", f)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r".*#+\s+WARN")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
