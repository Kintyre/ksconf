#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import EXIT_CODE_SUCCESS, EXIT_CODE_FAILED_SAFETY_CHECK
from tests.cli_helper import TestWorkDir, static_data, ksconf_cli


class CliKsconfUnarchiveTestCase(unittest.TestCase):
    '''
    def __init__(self, *args, **kwargs):
        super(CliKsconfUnarchiveTestCase, self).__init__(*args, **kwargs)
        self._modsec_workdir = TestWorkDir(git_repo=True)
    '''


    @classmethod
    def setUpClass(cls):
        # Tell the VC/git module that unit testing is in progress and therefore don't run git
        # command with the sole purpose of dumping junk to to the terminal.  Only run if unit
        # testing is actually invoked.
        import ksconf.vc.git
        ksconf.vc.git.unitesting = True

    def setUp(self):
        # Setup environmental variables to avoid GIT commit errors regarding missing user.email, user.name configs
        env = os.environ
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "Ksconf Unit Tests"
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "automated-tests@bogus.kintyre.co"

    def tearDown(self):
        env = os.environ
        for v in (
        "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            del env[v]

    def test_modsec_install_upgrade(self):
        twd = TestWorkDir(git_repo=True)
        self._modsec01_install_11(twd)
        self._modsec01_untracked_files(twd)
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_12.tgz")
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_14.tgz")

    def _modsec01_install_11(self, twd):
        """ Fresh app install a manual commit. """
        apps = twd.makedir("apps")
        tgz = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", tgz, "--dest", apps, "--git-mode=stage")
            self.assertIn("About to install", kco.stdout)
            self.assertIn("ModSecurity Add-on", kco.stdout,
                          "Should display app name during install")
        twd.write_file(".gitignore", "*.bak")
        twd.git("add", "apps/Splunk_TA_modsecurity", ".gitignore")
        twd.git("commit", "-m", "Add custom file.")
        twd.write_file("Junk.bak", "# An ignored file.")

    def _modsec01_untracked_files(self, twd):
        twd.write_file("apps/Splunk_TA_modsecurity/untracked_file", "content")
        twd.write_file("apps/Splunk_TA_modsecurity/ignored.bak", "Ignored file")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", static_data("apps/modsecurity-add-on-for-splunk_12.tgz"),
                             "--dest", twd.get_path("apps"), "--git-sanity-check=ignored",
                             "--git-mode=commit", "--no-edit")
            self.assertEqual(kco.returncode, EXIT_CODE_FAILED_SAFETY_CHECK)
            # Rollback upgrade and try again
            twd.git("reset", "--hard", "HEAD")
            # Remove offending files
            twd.remove_file("apps/Splunk_TA_modsecurity/untracked_file")
            twd.remove_file("apps/Splunk_TA_modsecurity/ignored.bak")
            kco = ksconf_cli("unarchive", static_data("apps/modsecurity-add-on-for-splunk_12.tgz"),
                             "--dest", twd.get_path("apps"), "--git-sanity-check", "ignored",
                             "--git-mode=commit", "--no-edit")
            self.assertEqual(kco.returncode, EXIT_CODE_SUCCESS)

    def _modsec01_upgrade(self, twd, app_tgz):
        """ Upgade app install with auto commit. """
        tgz = static_data(app_tgz)
        with ksconf_cli:
            kco = ksconf_cli("unarchive", tgz, "--dest", twd.get_path("apps"),
                             "--git-mode=commit", "--no-edit")
            self.assertIn("About to upgrade", kco.stdout)

    def test_zip_file(self):
        # Note:  Very minimal .zip testing since using the ZIP format is rare but does happen.
        # Sometimes a user will grab a zip file from a GitHub download, so we cope if we can.
        twd = TestWorkDir()  # No git, keeping it as simple as possible (also, test that code path)
        zfile = static_data("apps/technology-add-on-for-rsa-securid_01.zip")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", zfile, "--dest", twd.makedir("apps"))
            self.assertIn("About to install", kco.stdout)
            self.assertIn("RSA Securid Splunk Addon", kco.stdout)
            self.assertRegex(kco.stdout, "without version control support")

    def test_modsec_install_defaultd(self):
        twd = TestWorkDir(git_repo=True)
        app_archives = [
            "apps/modsecurity-add-on-for-splunk_11.tgz",
            "apps/modsecurity-add-on-for-splunk_12.tgz",
            "apps/modsecurity-add-on-for-splunk_14.tgz",
        ]
        apps = twd.makedir("apps")
        for app in app_archives:
            tgz = static_data(app)
            with ksconf_cli:
                kco = ksconf_cli("unarchive", tgz, "--dest", apps, "--git-mode=commit", "--no-edit",
                                 "--default-dir", "default.d/10-official",
                                 "--exclude", "README/inputs.conf.spec")
                self.assertEqual(kco.returncode, EXIT_CODE_SUCCESS)
                self.assertRegex(kco.stdout, "with git support")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
