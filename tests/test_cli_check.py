#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import unittest
import os
import sys

from io import StringIO

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *


class CliCheckTest(unittest.TestCase):

    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.conf_bad = twd.write_file("badfile.conf", """
        # Invalid entry 'BAD_STANZA'
        [BAD_STANZA
        a = 1
        b = 2
        """)
        self.conf_good = twd.write_conf("goodfile.conf", {
            GLOBAL_STANZA: {"c": 3},
            "x": {"a": 1, "b": 2},
            "y": {"a": 1}
        })

    def test_check_just_good(self):
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

    def test_check_just_bad(self):
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegex(ko.stdout, r"\b1 files failed")
            self.assertRegex(ko.stderr, r"badfile\.conf:\s+[^:]+:\s+\[BAD_STANZA")

    def test_mixed(self):
        """ Make sure that if even a single file files, the exit code should be "BAD CONF" """
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good, self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_mixed_stdin(self):
        """ Make sure that if even a single file fails the exit code should be "BAD CONF" """
        instream = StringIO("\n".join([self.conf_good, self.conf_bad]))
        with FakeStdin(instream):
            with ksconf_cli:
                ko = ksconf_cli("check", "-")
                self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
                self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_mixed_quiet(self):
        """ Make sure that if even a single file fails the exit code should be "BAD CONF" """
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good, self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_mixed_quiet_missing(self):
        """ Test with a missing file """
        with ksconf_cli:
            # Yes, this may seem silly, a fresh temp dir ensures this file doesn't actually exist
            fake_file = self.twd.get_path("not-a-real-file.conf")
            ko = ksconf_cli("check", self.conf_good, fake_file)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stderr, r"Skipping missing file: [^\r\n]+[/\\]not-a-real-file.conf")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
