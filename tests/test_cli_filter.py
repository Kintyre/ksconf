#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import unittest
import re

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import *
from tests.cli_helper import *

class CliKsconfFilter(unittest.TestCase):

    _sample01 = """\
    #   Version 7.2.0
    [Errors in the last 24 hours]
    search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
    dispatch.earliest_time = -1d
    disabled = 1

    [Errors in the last hour]
    search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
    dispatch.earliest_time = -1h

    [Messages by minute last 3 hours]
    search = index=_internal source="*metrics.log" eps "group=per_source_thruput" NOT filetracker | eval events=eps*kb/kbps | timechart fixedrange=t span=1m limit=5 sum(events) by series
    dispatch.earliest_time = -3h
    displayview = report_builder_display

    [Splunk errors last 24 hours]
    search = index=_internal " error " NOT debug source=*splunkd.log*
    dispatch.earliest_time = -24h
    """

    def setUp(self):
        self.twd = TestWorkDir()

    def tearDown(self):
        # Cleanup test working directory
        self.twd.clean()

    @property
    def sample01(self):
        return self.twd.write_file("savedsearches.conf", self._sample01)

    def test_filter_stanas(self):
        "Test simple stanza filter"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in the last hour")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertIn("Errors in the last hour", out)

    def test_mode_regex(self):
        "Regex stanza filter"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "^Errors.*", "--match", "regex")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertIn("Errors in the last hour", out)
            self.assertIn("Errors in the last 24 hours", out)
            self.assertNotIn("Splunk errors last 24 hours", out)

    def test_mode_string(self):
        "String stanza filter"
        sample01 = self.sample01
        with ksconf_cli:
            ko = ksconf_cli("filter", sample01, "--match", "string",
                            "--stanza", "Messages by minute last 3 hours")
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 1, "Expect exactly one output stanza")
            self.assertIn("Messages by minute last 3 hours", out)

            # Test multiple '--stanza'
            ko = ksconf_cli("filter", sample01, "--match", "string",
                            "--stanza", "Messages by minute last 3 hours",
                            "--stanza", "Errors in the last hour")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 2, "Expecting 2 stanzas")
            self.assertIn("Messages by minute last 3 hours", out)
            self.assertIn("Errors in the last hour", out)

            # Make sure that there are no substring matches
            ko = ksconf_cli("filter", sample01, "--match", "string",
                            "--stanza", "in the last")
            out = ko.get_conf()
            self.assertEqual(len(out), 0, "Expected 0 stanzas for a substring/partial string")

    def test_mode_wildcard(self):
        "Wildcard stanza filter"
        sample01 = self.sample01
        with ksconf_cli:
            ko = ksconf_cli("filter", sample01, "--match", "wildcard",
                            "--stanza", "Errors in *")
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 2, "Prefix of 'Errors in *' should return 2 matches")
            self.assertIn("Errors in the last hour", out)
            self.assertIn("Errors in the last 24 hours", out)

            # Test multiple '--stanza'
            ko = ksconf_cli("filter", sample01, "--match", "wildcard",
                            "--stanza", "*by minute last ? hours",
                            "--stanza", "Errors*")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 3, "Expecting 3 stanzas")
            self.assertIn("Messages by minute last 3 hours", out)
            self.assertIn("Errors in the last hour", out)
            self.assertIn("Errors in the last 24 hours", out)

            # Test multiple wildcards in a single pattern
            ko = ksconf_cli("filter", sample01, "--match", "wildcard",
                            "--stanza", "*last*")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 4, "Expecting all 4 stanzas")

            # Make sure that there are no substring matches
            ko = ksconf_cli("filter", sample01, "--match", "wildcard",
                            "--stanza", "in the last")
            out = ko.get_conf()
            self.assertEqual(len(out), 0, "Expected 0 stanzas for a substring/partial string")

    def test_mode_regex_ignorecase(self):
        "Regex stanza filter case insensitive"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", r".*\bErrors\b.*",
                            "--match", "regex", "--ignore-case")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 3)
            self.assertIn("Errors in the last hour", out)
            self.assertIn("Errors in the last 24 hours", out)
            self.assertIn("Splunk errors last 24 hours", out)

    def test_mode_string_ignorecase(self):
        "String stanza filter case insensitive"
        sample01 = self.sample01
        with ksconf_cli:
            args = ["filter", sample01, "--match", "string",
                     "--stanza", "MESSAGES by minute last 3 HOURS"]
            ko = ksconf_cli(*args)
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 0, "Case mismatch.  Shouldn't match")

            # Same test with the "-i" flag added; should now match
            args.append("-i")
            ko = ksconf_cli(*args)
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 1, "Expect exactly one output stanza")
            self.assertIn("Messages by minute last 3 hours", out)

    def test_mode_wildcard_ignorecase(self):
        "Wildcard stanza filter case insensitive"
        sample01 = self.sample01
        with ksconf_cli:
            ko = ksconf_cli("filter", sample01, "--ignore-case", "--match", "wildcard",
                            "--stanza", "*Errors*")
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 3)
            self.assertIn("Errors in the last hour", out)
            self.assertIn("Errors in the last 24 hours", out)
            self.assertIn("Splunk errors last 24 hours", out)


    def test_match_from_flat_file(self):
        "Load a list of stanzas to keep from a text file"
        flatfile = self.twd.write_file("important_stanzas", """
        Splunk errors last 24 hours
        Messages by minute last 3 hours
        """)
        # Test multiple '--stanza'
        ko = ksconf_cli("filter", self.sample01, "--match", "string",
                        "--stanza", "file://{}".format(flatfile))
        self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
        out = ko.get_conf()
        self.assertEqual(len(out), 2, "Expecting 2 stanzas")
        self.assertIn("Splunk errors last 24 hours", out)
        self.assertIn("Messages by minute last 3 hours", out)

    @property
    def props01(self):
        return self.twd.write_file("default/props.conf", r"""
        [apache]
        SHOULD_LINEMERGE = true
        BREAK_ONLY_BEFORE = ^\[
        TIME_FORMAT = [%A %B %d %T %Y]

        [iis]
        SHOULD_LINEMERGE = False
        INDEXED_EXTRACTIONS = w3c
        """)

    @property
    def props02(self):
        return self.twd.write_file("local/props/conf", """
        [splunkd]
        MAX_TIMESTAMP_LOOKAHEAD = 40
        TIME_FORMAT = %m-%d-%Y %H:%M:%S.%l %z
        [iis]
        SHOULD_LINEMERGE = True
        category = Web
        detect_trailing_nulls = auto
        """)

    def test_multiple_inputs(self):
        "Ensure that multiple inputs are handled correctly"
        with ksconf_cli:
            ko = ksconf_cli("filter", "--stanza", "iis", self.props01, self.props02)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            stanzas = re.findall(r'(?:^|[\r\n]+)\[iis\][\r\n]+', ko.stdout)
            self.assertEqual(len(stanzas), 2)

    def test_filter_invert_mode(self):
        "Test match inversion"
        with ksconf_cli:
            ko = ksconf_cli("filter", "--invert-match", "--stanza", "iis",
                            self.props01, self.props02)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 2)   # Expecting 2 stanzas
            self.assertIn("splunkd", out)
            self.assertIn("apache", out)

    def test_invert_full_circle(self):
        "Confirm that match + inverted match = original"
        conf = self.sample01
        matched = self.twd.get_path("output-match.conf")
        rejected = self.twd.get_path("output-rejected.conf")

        with ksconf_cli:
            # Simple direct stanza match (saved to an output file)
            ko = ksconf_cli("filter", conf, "--stanza", "Errors in the last hour",
                            "--output", matched)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = self.twd.read_conf("output-match.conf")
            self.assertEqual(len(out), 1)

            # Inversion of the above (saved to a different file)
            ko = ksconf_cli("filter", conf, "--stanza", "Errors in the last hour",
                            "--invert-match", "--output", rejected)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = self.twd.read_conf("output-rejected.conf")
            self.assertEqual(len(out), 3)

            # Combine 2 output files, then compare to original
            merged = self.twd.get_path("output-merged.conf")
            ko = ksconf_cli("merge", matched, rejected, "--target", merged)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

            # Compare merged file to the original file
            ko = ksconf_cli("diff", conf, merged)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_EQUAL)

    def test_conf_via_stdin(self):
        "Stream in an input file over stdin"
        with FakeStdin(self._sample01):
            with ksconf_cli:
                ko = ksconf_cli("filter", "-", "--stanza", "Errors in the last hour")
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf()
                self.assertIn("Errors in the last hour", out)

    def test_has_attr(self):
        "Keep all stanzas with given attribute"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props01, "--attr-present", "BREAK_ONLY_*")
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 1)
            self.assertIn("apache", out)
            self.assertEqual(out["apache"]["BREAK_ONLY_BEFORE"], r"^\[")

    def test_has_attr_inverse(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props01, "-v", "--attr-present", "BREAK_ONLY_*")
            out = ko.get_conf()
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 1)
            self.assertNotIn("apache", out)



if __name__ == '__main__':  # pragma: no cover
    unittest.main()
