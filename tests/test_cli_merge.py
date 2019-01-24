#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import unittest
import os
import sys

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *





class CliMergeTest(unittest.TestCase):
    def test_merge_to_stdout(self):
        twd = TestWorkDir()
        conf1 = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        conf2 = twd.write_file("inputs2.conf", """
        [script://./bin/ps.sh]
        disabled = FALSE
        inverval = 97
        index = os_linux
        """)
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"[\r\n]disabled = FALSE")

    def test_merge_dry_run(self):
        twd = TestWorkDir()
        conf1 = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        conf2 = twd.write_file("inputs2.conf", """
        [script://./bin/ps.sh]
        disabled = FALSE
        inverval = 97
        index = os_linux
        """)
        newfile = twd.get_path("input-new.conf")
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile, "--dry-run")

            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # Todo: Figure out if this should be a "+" or "-"....
            self.assertRegex(ko.stdout, r"[\r\n][+-]disabled = FALSE")

        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"^$")

if __name__ == '__main__':  # pragma: no cover
    unittest.main()
