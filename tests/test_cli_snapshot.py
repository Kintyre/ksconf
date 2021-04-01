#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import EXIT_CODE_NO_SUCH_FILE, EXIT_CODE_SUCCESS
from tests.cli_helper import TestWorkDir, ksconf_cli


class CliKsconfSnapshotTest(unittest.TestCase):

    def test_app_simple(self):
        twd = TestWorkDir()
        twd.write_file("apps/MyApp/default/app.conf", """\
        [install]
        is_configured = false
        state = disabled
        build = 1

        [launcher]
        author = Kintyre
        version = 0.6.0
        description = Custom IT Events add-on for db connect events.  Includes CIM compliance for ES.

        [ui]
        is_visible = true
        label = CLIENT IT Events add-on
        """)
        twd.write_file("apps/MyApp/local/app.conf", """\
        [install]
        is_configured = true
        state = enabled

        [ui]
        is_visible = false
        """)
        twd.write_file("apps/MyApp/local/props.conf", """\
        # very bad idea...
        SHOULD_LINEMERGE = true
        """)

        twd.write_file("apps/MyApp/metadata/local.meta", """\
        []
        export = system
        """)
        with ksconf_cli:
            ko = ksconf_cli("snapshot", twd.get_path("apps"))
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # Load output as JSON

            d = json.loads(ko.stdout)
            self.assertTrue(d["records"])
            self.assertTrue(d["schema_version"] > 0)
            self.assertTrue(d["software"])
        # Make sure minimize mode doesn't die
        with ksconf_cli:
            ko = ksconf_cli("snapshot", "--minimize", twd.get_path("apps"))
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            json.loads(ko.stdout)

    def test_single_file_mode(self):
        twd = TestWorkDir()
        fn = twd.write_file("apps/MyApp/default/app.conf", """\
        [install]
        is_configured = false
        state = disabled
        build = 1
        """)
        with ksconf_cli:
            ko = ksconf_cli("snapshot", fn)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # Load output as JSON
            d = json.loads(ko.stdout)
            self.assertTrue(d["records"])

    def test_bad_conf_file(self):
        twd = TestWorkDir()
        twd.write_file("apps/MyApp/default/crap.conf", """\
        happy = 0
        [the start of something beautiful
        """)
        twd.write_file("apps/MyApp/default/not-a-conf-file.txt", "Nothing to see here!")
        twd.makedir("apps/MyApp/bin")
        with ksconf_cli:
            ko = ksconf_cli("snapshot", twd.get_path("apps"))
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # XXX:  Add a better failure test here...
            self.assertRegex(ko.stdout, r"\"failure\"\s*:\s*\"")
            json.loads(ko.stdout)

    def test_missing_conf_file(self):
        twd = TestWorkDir()
        with ksconf_cli:
            ko = ksconf_cli("snapshot", twd.get_path("not/a/file.conf"))
            self.assertEqual(ko.returncode, EXIT_CODE_NO_SUCH_FILE)
            self.assertRegex(ko.stderr, r"No such file")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
