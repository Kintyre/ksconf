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
    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        self.twd.clean()
        del self.twd

    @property
    def transforms_sample1(self):
        return self.twd.write_file("transforms.conf", """
        [single_quote_kv]
        REGEX = ([^=\s]+)='([^']+)'
        FORMAT = $1::$2
        MV_ADD = 0
        """)

    @property
    def props_sample1(self):
        return self.twd.write_file("props.conf", """
        [syslog]
        REPORT-single-quote = single_quote_kv
        REPORT-group2 = more_extract
        EXTRACT-pid = \[(?<pid>\d+)\]
        """)

    def test_simple_transforms_insert(self):
        with ksconf_cli:
            ko = ksconf_cli("rest-export", self.transforms_sample1)
            # XXX:  Check for more things...
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"([\r\n]+|^)curl -k")
            # Should use 'name' for stanza, and not be embedded in URL
            self.assertRegex(ko.stdout, r"name=single_quote_kv")
            # Make sure fancy regex is encoded as expected
            self.assertIn("%5B%5E%3D%5Cs%5D%2B", ko.stdout)
            self.assertNotRegex(ko.stdout, r"https://[^ ]+/single_quote_kv ")

    def test_simple_transforms_update(self):
        with ksconf_cli:
            ko = ksconf_cli("rest-export", "--update", self.transforms_sample1)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"([\r\n]+|^)curl ")
            self.assertRegex(ko.stdout, r"https://[^ ]+/single_quote_kv ")
            self.assertNotRegex(ko.stdout, r"name=single_quote_kv")

    def test_simple_transforms_delete(self):
        with ksconf_cli:
            ko = ksconf_cli("rest-export", "--delete", self.transforms_sample1)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"([\r\n]+|^)curl ")
            self.assertRegex(ko.stdout, r"https://[^ ]+/single_quote_kv ")
            self.assertRegex(ko.stdout, r"-X\s+DELETE")

    def test_auth_template_prefix(self):
        with ksconf_cli:
            # Confirm that sample SPLUNKDAUTH template text is present
            ko = ksconf_cli("rest-export", self.transforms_sample1)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, "SPLUNKDAUTH=\$\(")

            # Confirm that sample SPLUNKDAUTH template text is removed upon request
            ko = ksconf_cli("rest-export", self.transforms_sample1, "--disable-auth-output")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertNotRegex(ko.stdout, "SPLUNKDAUTH=\$\(")

    def test_warn_on_global_entry(self):
        f = self.twd.write_file("props.conf", """
        EVAL-always_present = 1
        [syslog]
        REPORT-single-quote = single_quote_kv
        """)
        with ksconf_cli:
            ko = ksconf_cli("rest-export", f)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r".*#+\s+WARN")

    def test_pretty_print(self):
        with ksconf_cli:
            ko = ksconf_cli("rest-export", self.props_sample1, "--pretty-print")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"\\[\r\n]+[\t ]*-d EXTRACT-pid=")

    def test_explicit_conf_type(self):
        f = self.twd.write_file("mysearches.conf", """
        [Do the thing]
        search = noop
        [Meaning of life]
        search = * | head 100 | stats
        """)
        for variations in [(), ["--update"], ["--pretty-print"]]:
            with ksconf_cli:
                ko = ksconf_cli("rest-export", "--conf", "savedsearches", f, *variations)
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                self.assertRegex(ko.stdout, r"curl[^\r\n]+/configs/conf-savedsearches[/ ]")

    def test_curl_args(self):
        with ksconf_cli:
            '''
            # Confirm that sample SPLUNKDAUTH template text is present
            ko = ksconf_cli("rest-export", self.transforms_sample1, "--extra-args=--retry 2")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"curl [^\r\n]+ --retry 2")
            '''

            ko = ksconf_cli("rest-export", self.transforms_sample1,
                            '--extra-args=-o "/tmp/temp file"')
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"curl [^\r\n]+ -o")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
