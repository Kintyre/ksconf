#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest
from glob import glob

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_SORT_APPLIED, EXIT_CODE_SUCCESS
from tests.cli_helper import TestWorkDir, ksconf_cli


class CliSortTest(unittest.TestCase):
    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.conf_bogus = twd.write_file("bogus.conf", """
        # Global comment 1
        global_entry1 = x
        global_entry2 = y
        # Global Comment 2

        [b]
        z = 1
        y = 2
        x = 3
        [a]
        x = 1
        y =2

        z=3
        """)
        self.conf_bad = twd.write_file("badfile.conf", """
        [my stanza]
        x = 3
        [BAD_STANZA
        a = 1
        b = 2
        [other]
        z = 9
        """)
        # This could eventually be a stanza-only sort with key-order preservation
        self.no_sort = twd.write_file("transforms.conf", r"""
        # KSCONF-NO-SORT
        [the-classic-header-nullqueue]
        REGEX = ^PalletId.*$
        DEST_KEY = queue
        FORMAT = nullQueue

        [assign_sourcetype_mytool_subservice]
        SOURCE_KEY = MetaData:Source
        REGEX = [/\\]([A-Za-z]+)\.txt(?:\.\d+)?(?:\.gz)?$
        DEST_KEY = MetaData:Sourcetype
        FORMAT = sourcetype::MyTool:Services:$1
        """)

        self.all_confs = glob(twd.get_path("*.conf"))

    def test_sort_inplace_returncodes(self):
        """ Inplace sorting long and short args """
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", self.conf_bogus)
            self.assertEqual(ko.returncode, EXIT_CODE_SORT_APPLIED)
            self.assertRegex(ko.stderr, "^Replaced file")
        # Sort the second time, no there should be NO updates
        with ksconf_cli:
            ko = ksconf_cli("sort", "--inplace", self.conf_bogus)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stderr, "^Nothing to update")

    def test_sort_glob(self):
        # Implemented in 0.7.7 for Windows.  Don't rely on shell for expansion
        glob_pattern = self.twd.get_path("*.conf")
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", glob_pattern)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegex(ko.stderr, r"(?i)error[^\r\n]+badfile\.conf")

    def test_bad_file(self):
        with ksconf_cli:
            ko = ksconf_cli("sort", self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_sort_mixed(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", *self.all_confs)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegex(ko.stderr,
                             r"Error [^\r\n]+? file [^\r\n]+?[/\\]badfile\.conf[^\r\n]+ \[BAD_STANZA")
            self.assertRegex(ko.stderr, r"Skipping no-sort file [^ ]+[/\\]transforms\.conf")

    def test_sort_stdout(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", self.conf_bogus, self.no_sort)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"-----+ [^\r\n]+[/\\]bogus\.conf")
            self.assertRegex(ko.stdout, r"[\r\n]-----+ [^\r\n]+[/\\]transforms\.conf")
            self.assertRegex(ko.stdout, r"[\r\n]DEST_KEY = [^\r\n]+[\r\n]FORMAT =",
                             "transforms.conf should be sorted even with KSCONF-NO-SORT directive for non-inplace mode")

    def test_sort_mixed_quiet(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", "--quiet", *self.all_confs)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegex(ko.stderr, r"Error [^\r\n]+?[/\\]badfile\.conf")
            self.assertNotRegex(ko.stderr, r"Skipping [^\r\n]+?[/\\]transforms\.conf")
            self.assertRegex(ko.stderr, r"[\r\n]Replaced file [^\r\n]+?\.conf")
        # No there should be NO output
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", "--quiet", self.conf_bogus, self.no_sort)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertNotRegex(ko.stderr, r"Error [^\r\n]+?\.conf")
            self.assertNotRegex(ko.stderr, r"[\r\n]Skipping [^\r\n]+?[/\\]transforms.conf")
            self.assertNotRegex(ko.stderr, r"[\r\n]Replaced file [^\r\n]+?\.conf")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
