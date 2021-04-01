#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import (EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_NO_SUCH_FILE,
                           EXIT_CODE_SUCCESS, EXIT_CODE_USER_QUIT)
from tests.cli_helper import FakeStdin, TestWorkDir, ksconf_cli


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
        interval = 8675309
        """)
        newfile = twd.copy_static("inputs-ta-nix-local.conf", "input-new.conf")
        # newfile = twd.get_path("input-new.conf")
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile, "--dry-run")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"[\r\n]\+disabled = FALSE")
            self.assertRegex(ko.stdout, r"[\r\n]\+interval = 8675309")
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stdout, r"^$")

    def test_magic_stanza_drop(self):
        twd = TestWorkDir()
        conf1 = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        conf2 = twd.write_file("inputs2.conf", """
        [script://./bin/ps.sh]
        _stanza = <<DROP>>
        """)
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            conf = ko.get_conf()
            self.assertNotIn("script://./bin/ps.sh", conf)

    def test_missing_file(self):
        twd = TestWorkDir()
        with ksconf_cli:
            # Missing files should be reported as an error, by default
            ko = ksconf_cli("merge", twd.get_path("a_non_existent_file.conf"))
            self.assertIn(ko.returncode, (EXIT_CODE_USER_QUIT, EXIT_CODE_NO_SUCH_FILE))
            self.assertRegex(ko.stderr, r".*\b(can't open '[^']+\.conf'|invalid ConfFileType).*")

            # Make sure that with --ignore-missing missing files are silently ignored
            ko = ksconf_cli("merge", "--ignore-missing", twd.get_path("a_non_existent_file.conf"))
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(ko.stdout.strip(), "")

    def test_invalid_conf(self):
        bad_conf = """
        [dangling stanza
        attr = 1
        bad file =  very true"""
        twd = TestWorkDir()
        badfile = twd.write_file("bad_conf.conf", bad_conf)
        with ksconf_cli:
            ko = ksconf_cli("merge", badfile)
            self.assertIn(ko.returncode, (EXIT_CODE_USER_QUIT, EXIT_CODE_BAD_CONF_FILE))
            self.assertRegex(ko.stderr, "([Ff]ailed to parse|invalid ConfFileType)")

            with FakeStdin(bad_conf):
                ko = ksconf_cli("merge", "-")
                self.assertIn(ko.returncode, (EXIT_CODE_USER_QUIT, EXIT_CODE_BAD_CONF_FILE))
                self.assertRegex(ko.stderr, "([Ff]ailed to parse|invalid ConfFileType)")

    def test_utf8bom(self):
        twd = TestWorkDir()
        conf = twd.write_file("test.conf",
                              b'\xef\xbb\xbf\n[ui]\n\n[launcher]\n\n[package]\ncheck_for_updates = 0\n')
        with ksconf_cli:
            ko = ksconf_cli("merge", conf)
            self.assertEqual(ko.returncode, 0)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
