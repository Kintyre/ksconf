#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import tarfile
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *


class CliPackageCmdTest(unittest.TestCase):

    @staticmethod
    def build_basic_app_01(twd, folder="default", metadata=False):
        twd.write_file(folder + "/savedsearches.conf", r"""
        [my_search]
        search = noop
        """)
        twd.write_file(folder + "/app.conf", r"""
        [ui]
        label = My cool app

        [launcher]
        author = lowell
        description = some text that barely shows up anywhere in splunk
        version = 0.0.1

        [package]
        id = my_app_on_splunkbase
        check_for_updates = 1
        """)
        twd.write_file(folder + "/data/ui/views/mrs_dash.xml", r"""
        <dashboard>
        <row>
        <table>
        <search>
        <query>index=fav sourcetype=seasoning</query>
        </table>
        </row>
        </dashboard>
        """)
        if metadata:
            twd.write_file("metadata/{}.meta".format(metadata), r"""
            []
            system = export
            """)

    def test_package_simple(self):
        twd = TestWorkDir()
        self.build_basic_app_01(twd, "default")
        with ksconf_cli:
            ko = ksconf_cli("package", twd.get_path("."),
                            "-f", twd.get_path("my_app_on_splunkbase-{{version}}.tgz"),
                            "--layer-method", "disable",
                            "--app-name", "my_app_on_splunkbase",
                            "--release-file", twd.get_path("release_file"))
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

        tarball = twd.read_file("release_file")
        self.assertTrue(tarball.endswith("my_app_on_splunkbase-0.0.1.tgz"))
        self.assertTrue(os.path.isfile(tarball))
        tf = tarfile.open(tarball, r":gz")

        names = tf.getnames()
        self.assertIn("my_app_on_splunkbase/default/app.conf", names)
        self.assertNotIn("my_app_on_splunkbase/local/app.conf", names)

    def test_package_simple_local(self):
        twd = TestWorkDir()
        self.build_basic_app_01(twd, "local", metadata="local")
        with ksconf_cli:
            ko = ksconf_cli("package", twd.get_path("."),
                            "-f", twd.get_path("my_app_on_splunkbase-{{version}}.spl"),
                            "--merge-local",
                            "--layer-method", "disable",
                            "--set-version", "1.2.3",
                            "--app-name", "my_app_on_splunkbase",
                            "--release-file", twd.get_path(".rf"))

            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
        tarball = twd.read_file(".rf")
        self.assertTrue(tarball.endswith("my_app_on_splunkbase-1.2.3.spl"))
        self.assertTrue(os.path.isfile(tarball))

        tf = tarfile.open(tarball, r":gz")
        names = tf.getnames()
        # Expected files
        self.assertIn("my_app_on_splunkbase/default/app.conf", names)
        self.assertIn("my_app_on_splunkbase/metadata/default.meta", names)
        # Ensure these files are NOT present
        self.assertNotIn("my_app_on_splunkbase/local/app.conf", names)
        self.assertNotIn("my_app_on_splunkbase/metadata/local.meta", names)
        # self.assertRegex(ko.stdout, r"^diff ", "Missing diff header line")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
