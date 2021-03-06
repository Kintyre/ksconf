#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from ksconf.consts import EXIT_CODE_MISSING_ARG, EXIT_CODE_SUCCESS
from tests.cli_helper import TestWorkDir, ksconf_cli, static_data


class CliMinimizeTest(unittest.TestCase):

    def test_minimize_cp_inputs(self):
        """ Test typical usage:  copy default-> local, edit, minimize """
        twd = TestWorkDir()
        local = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        default = static_data("inputs-ta-nix-default.conf")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--dry-run", "--target", local, default)
            self.assertRegex(ko.stdout, r"[\r\n][ ]\[script://\./bin/ps\.sh\]")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--output", twd.get_path("inputs-new.conf"),
                            "--target", local, default)
            d = twd.read_conf("inputs-new.conf")
            self.assertIn("script://./bin/version.sh", d)
            self.assertIn("script://./bin/vmstat.sh", d)
            self.assertIn("script://./bin/ps.sh", d)
            self.assertIn("script://./bin/iostat.sh", d)
            self.assertEqual(d["script://./bin/iostat.sh"]["interval"], "300")
            self.assertEqual(d["script://./bin/netstat.sh"]["interval"], "120")
            self.assertEqual(d["script://./bin/netstat.sh"]["disabled"], "0")

    def test_minimize_reverse(self):
        twd = TestWorkDir()
        local = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        default = static_data("inputs-ta-nix-default.conf")
        inputs_min = twd.get_path("inputs-new.conf")
        rebuilt = twd.get_path("inputs-rebuild.conf")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--output", inputs_min,
                            "--target", local, default)
        with ksconf_cli:
            ko = ksconf_cli("merge", "--target", rebuilt, default, inputs_min)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
        with ksconf_cli:
            ko = ksconf_cli("diff", static_data("inputs-ta-nix-local.conf"), rebuilt)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

    def test_remove_empty_stanza(self):
        twd = TestWorkDir()
        conf1 = twd.write_file("props1.conf", """\
        [stanza1]
        a = 99
        z = 34
        x = apple

        [stanza2]
        a = 99

        [stanza3]

        [stanza4]
        """)
        conf2 = twd.write_file("props2.conf", """\
        [stanza1]
        a = 99
        z = 34
        x = apple

        [stanza2]
        # Keep this one, even with NO overlap
        b = friendly bear

        [stanza3]
        """)
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--target", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            d = twd.read_conf("props1.conf")
            self.assertEqual(d["stanza2"]["a"], "99")
            self.assertNotIn("b", d["stanza2"])
            self.assertNotIn("stanza1", d)
            self.assertNotIn("stanza3", d)  # Empty in both, therefore identical, so remove it
            self.assertIn("stanza4", d)  # Unique to props1, so preserve!

    @unittest.expectedFailure
    def test_remove_with_comments(self):
        # Comments are currently lost.  Not 100% what the correct behavior should be
        twd = TestWorkDir()
        conf1 = twd.write_file("props1.conf", """\
        [no_comments]
        a = 1

        [comments_in_1]
        # Yes I DO!
        a = 1

        [comments_in_2]
        a = 1

        [comments_in_both]
        # Comments

        [fav_color]
        # seafoam
        """)
        conf2 = twd.write_file("props2.conf", """\
        [no_comments]
        a = 1

        [comments_in_1]
        a = 1

        [comments_in_2]
        # here are comments, as promised!
        a = 1

        [comments_in_both]
        # Comments

        [fav_color]
        # aqua
        """)
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--target", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            d = twd.read_conf("props1.conf")
            self.assertNotIn("no_comments", d)
            self.assertNotIn("comments_in_1", d)
            self.assertNotIn("comments_in_2", d)

            # These are currently failing:
            self.assertNotIn("comments_in_both", d)
            self.assertNotIn("fav_color", d)

    def test_minimize_explode_defaults(self):
        twd = TestWorkDir()
        conf = twd.write_file("savedsearches.conf", """\
        [License usage trend by sourcetype]
        action.email.useNSSubject = 1
        alert.track = 0
        disabled = 0
        enableSched = 0
        dispatch.earliest_time = -30d@d
        dispatch.latest_time = now
        display.general.type = visualizations
        display.page.search.tab = visualizations
        display.statistics.show = 0
        display.visualizations.charting.chart = area
        display.visualizations.charting.chart.stackMode = stacked
        request.ui_dispatch_app = kintyre
        request.ui_dispatch_view = search
        search = | tstats sum(b) as bytes where index=summary_splunkidx by st, _time span=1h | timechart span=1h sum(eval(bytes/1073741824)) as b by st | foreach * [ eval "<<FIELD>>"=round('<<FIELD>>',2) ]
        """)
        sysdefault = static_data("savedsearches-sysdefault70.conf")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--dry-run", "--explode-default", "--target", conf, sysdefault)
            self.assertRegex(ko.stdout, r"[\r\n]-disabled")
            self.assertRegex(ko.stdout, r"[\r\n]-enableSched")
        orig_size = os.stat(conf).st_size
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--explode-default", "--target", conf, sysdefault)
            final_size = os.stat(conf).st_size
            self.assertTrue(orig_size > final_size)

    def test_missing_target(self):
        twd = TestWorkDir()
        local = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        default = static_data("inputs-ta-nix-default.conf")
        inputs_min = twd.get_path("inputs-new.conf")
        # rebuilt = twd.get_path("inputs-rebuild.conf")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--output", inputs_min, local, default)
            self.assertEqual(ko.returncode, EXIT_CODE_MISSING_ARG)
            self.assertIn("--target", ko.stderr)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
