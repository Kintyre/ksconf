#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import re
import sys
import unittest

try:
    # Python 3.3+
    from unittest import mock
except ImportError:
    # Add on for earlier versions
    import mock

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.conf.parser import PARSECONF_STRICT
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
        "Test simple stanza filter (wildcard is the default)"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in the last *")
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

    def test_no_match(self):
        "No match (with verbose) should be reported to stderr"
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "NOT A REAL STANZA", "--verbose")
            out = ko.get_conf()
            # Should the exit code be different here?
            # self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertEqual(len(out), 0)
            self.assertRegex(ko.stderr, "No matching stanzas")

            # Same test but with "-l" added
            ko = ksconf_cli("filter", self.sample01, "--stanza", "BOGUS", "--verbose", "-l")
            self.assertRegex(ko.stderr, "No matching stanzas")

    def test_match_from_flat_file(self):
        "Load a list of stanzas to keep from a text file"
        flatfile = self.twd.write_file("important_stanzas", """
        Splunk errors last 24 hours
        Messages by minute last 3 hours
        """)
        with ksconf_cli:
            # Test multiple '--stanza'
            ko = ksconf_cli("filter", "--verbose", self.sample01, "--match", "string",
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
            self.twd.read_file("output-match.conf", as_bytes=True)  # Boost code coverage
            self.assertEqual(len(out), 3)

            # Combine 2 output files, then compare to original
            merged = self.twd.get_path("output-merged.conf")
            ko = ksconf_cli("merge", matched, rejected, "--target", merged)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

            # Compare merged file to the original file
            ko = ksconf_cli("diff", conf, merged)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_EQUAL)

    def test_output_linecount(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, self.props02, "--stanza", "Errors in *", "-l")
            self.assertRegex(ko.stdout, r"[/\\]savedsearches.conf[\r\n]")

    def test_output_count(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in *", "-c")
            self.assertEqual(int(ko.stdout), 2)

    def test_output_brief(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in *", "-b")
            self.assertRegex(ko.stdout, r"Errors in the last hour[\r\n]")
            self.assertRegex(ko.stdout, r"Errors in the last 24 hours[\r\n]")

    def test_output_list_combos(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in *", "-l", "-b")
            self.assertRegex(ko.stdout, r"savedsearches.conf:\s*Errors in the last hour[\r\n]")
            self.assertRegex(ko.stdout, r"savedsearches.conf:\s*Errors in the last 24 hours[\r\n]")

            ko = ksconf_cli("filter", self.sample01, "--stanza", "Errors in *", "-l", "-c")
            self.assertRegex(ko.stdout, r"savedsearches.conf(:| has)\s*2\s")

    def test_conf_via_stdin(self):
        "Stream in an input file over stdin"
        with FakeStdin(self._sample01):
            with ksconf_cli:
                ko = ksconf_cli("filter", "-", "--stanza", "Errors in the last hour")
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf(PARSECONF_STRICT)     # explict profile to boost coverage
                self.assertIn("Errors in the last hour", out)

    """ # This fails because it grabs the REAL STDIN and bypasses our FakeStdin context manager...
    @unittest.skipIf(sys.platform not in("darwin", "linux"), "Only runs on NIX")
    def test_conf_via_dev_stdin(self):
        "Stream in an input file over explicit device name (/dev/stdin)"
        # This also works for anon  files using bash's '<(CMD)' format (/dev/fd/nn)
        with FakeStdin(self._sample01):
            with ksconf_cli:
                ko = ksconf_cli("filter", "/dev/stdin", "--stanza", "Errors in the last hour")
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf(PARSECONF_STRICT)     # explicit profile to boost coverage
                self.assertIn("Errors in the last hour", out)
    """

    @unittest.skipIf(sys.platform not in ("darwin", "linux"), "Only runs on NIX")
    def test_conf_via_dev_fd_mock(self):
        "Stream in an input file over explicit FD:   /dev/fd/xx to simulate a bash '<(cmd)' input."
        # We must tell the OS that "/dev/fd/xxx" is NOT a file, which technically it is for the
        # moment since we're testing with an actual file; unlike '<(cmd)' where it would be a PIPE

        # Approach (failed); replace isfile() with my custom version:  (which looks for /dev/fd*)
        '''  # Causes unicode/str error ... weird
        def my_isfile(path):
            if path.startswith("/dev/fd"):
                return False
            return os.path.isfile(path)
        '''
        f = open(self.sample01)
        fd_dev = "/dev/fd/{}".format(f.fileno())
        try:
            with mock.patch("ksconf.commands.os.path.isfile") as m, ksconf_cli:
                m.return_value = False
                # m.wraps = my_isfile
                ko = ksconf_cli("filter", fd_dev, "--stanza", "Errors in the last hour")
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf(PARSECONF_STRICT)
                self.assertIn("Errors in the last hour", out)
        finally:
            if not f.closed:
                f.close()
            del f

    @unittest.skipIf(sys.platform not in ("darwin", "linux"), "Only runs on NIX")
    def test_conf_via_dev_fd_ext_cat(self):
        "Stream in an input file over pipe /dev/fd/xx.  Simulates a bash '<(cmd)' input"
        # XXX:  EXACT SAME TEST as test_conf_via_dev_fd_mock; long-term there's no need to keep both.
        #       For now just testing if we see any issues on different OS-es

        # We're launching a subprocess "cat" to create a pipe for ksconf to read from.  If we just
        # do a plain file-open and try to use that descriptor, os.path.isfile() still detects that
        # it's a regular file.

        # Another possible implementation is to use mock objects.  I started down that path and it
        # failed too.  (Also adding mock would require some new dependencies for py <3.3
        from subprocess import PIPE, Popen
        p = Popen(["cat", self.sample01], stdout=PIPE)
        fd = p.stdout.fileno()
        fd_dev = "/dev/fd/{}".format(fd)
        try:
            with ksconf_cli:
                ko = ksconf_cli("filter", fd_dev, "--stanza", "Errors in the last hour")
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf(PARSECONF_STRICT)     # explict profile to boost coverage
                self.assertIn("Errors in the last hour", out)
        finally:
            # Do we need this?
            # idk.  Calling p.communicate() seems weird here, but it causes all fd to be closed,
            # vs p.wait() causes unittest to give unclosed file warnings.
            p.communicate()

    def test_has_attr(self):
        "Keep all stanzas with given attribute"
        # Test with and without case sensitivity
        for extra_args in (["--attr-present", "BREAK_ONLY_*"],
                           ["--attr-present", "break_only_*", "-i"]):
            with ksconf_cli:
                ko = ksconf_cli("filter", self.props01, *extra_args)
                self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
                out = ko.get_conf()
                self.assertEqual(len(out), 1)
                self.assertIn("apache", out)
                self.assertEqual(out["apache"]["BREAK_ONLY_BEFORE"], r"^\[")

    def test_has_attr_inverse(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props01, "-v", "--attr-present", "BREAK_ONLY_*")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out), 1)
            self.assertNotIn("apache", out)

    @property
    def props03(self):
        return self.twd.write_file("props.conf", """
        [statsd]
        METRICS_PROTOCOL = statsd
        NO_BINARY_CHECK = true
        SHOULD_LINEMERGE = false
        TIMESTAMP_FIELDS = false
        DATETIME_CONFIG = CURRENT
        # remove indextime fields that aren't super useful.
        ADD_EXTRA_TIME_FIELDS = false
        ANNOTATE_PUNCT = false
        disabled = false
        pulldown_type = true
        category = Metrics
        description = Statsd daemon output format. Accepts the plain StatsD line metric protocol or the StatsD line metric protocol with dimensions extension.

        [collectd_http]
        METRICS_PROTOCOL = collectd_http
        NO_BINARY_CHECK = true
        SHOULD_LINEMERGE = false
        ADD_EXTRA_TIME_FIELDS = false
        ANNOTATE_PUNCT = false
        disabled = false
        pulldown_type = true
        TIMESTAMP_FIELDS = time
        KV_MODE=none
        category = Metrics
        description = Collectd daemon format. Uses the write_http plugin to send metrics data to a Splunk platform data input via the HTTP Event Collector.

        [kvstore]
        SHOULD_LINEMERGE = false
        TIMESTAMP_FIELDS = datetime
        TIME_FORMAT = %m-%d-%Y %H:%M:%S.%l %z
        INDEXED_EXTRACTIONS = json
        KV_MODE = none
        TRUNCATE = 1000000
        JSON_TRIM_BRACES_IN_ARRAY_NAMES = true
        """)

    def test_filter_attrs_keep(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props03, "--keep-attrs", "SHOULD_LINEMERGE")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            self.assertEqual(len(out["collectd_http"]), 1)
            self.assertEqual(len(out["statsd"]), 1)
            self.assertEqual(len(out["kvstore"]), 1)
            self.assertEqual(list(out["kvstore"]), ["SHOULD_LINEMERGE"])

    def test_filter_attrs_rejected(self):
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props03,
                            "--reject-attrs", "METRICS_PROTOCOL NO_BINARY_CHECK")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            keys = set()
            for i in out.values():
                keys.update(i)
            self.assertNotIn("METRICS_PROTOCOL", keys)
            self.assertNotIn("NO_BINARY_CHECK", keys)
            self.assertIn("ANNOTATE_PUNCT", keys)
            self.assertIn("JSON_TRIM_BRACES_IN_ARRAY_NAMES", keys)

    def test_filter_attrs_whbllist(self):
        """ Confirm that 'reject' is applied after 'keep'"""
        with ksconf_cli:
            ko = ksconf_cli("filter", self.props03, self.props02, "--ignore-case",
                            "--keep-attrs", "*TIME*",
                            "--keep-attrs", "*FIELD*",
                            "--reject-attrs", "TIME_FORMAT")
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            out = ko.get_conf()
            keys = set()
            for i in out.values():
                keys.update(i)
            self.assertNotIn("TIME_FORMAT", keys)
            self.assertIn("TIMESTAMP_FIELDS", keys)
            self.assertIn("ADD_EXTRA_TIME_FIELDS", keys)
            self.assertIn("DATETIME_CONFIG", keys)
            self.assertEqual(len(out["iis"]), 0)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
