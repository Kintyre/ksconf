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


class CliDiffTest(unittest.TestCase):
    def test_diff_simple_savedsearch(self):
        """ Do a simple comparison of a single stanza; also test color TTY mode. """
        twd = TestWorkDir()
        conf1 = twd.write_file("savedsearches-1.conf", """
        [x]
        search = noop
        """)
        conf2 = twd.write_file("savedsearches-2.conf", r"""
        [x]
        search = tstats count where index=hippo by sourcetype, source \
        | stats values(source) by sourcetype
        """)
        with ksconf_cli:
            ko = ksconf_cli("diff", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
            self.assertRegex(ko.stdout, r"^diff ", "Missing diff header line")
            self.assertRegex(ko.stdout, r"[\r\n]--- [^\r\n]+?[/\\]savedsearches-1.conf\s+\d{4}-\d\d-\d\d")
            self.assertRegex(ko.stdout, r"\+\+\+ [^\r\n]+?[/\\]savedsearches-2.conf\s+\d{4}-\d\d-\d\d")
            self.assertRegex(ko.stdout, r"[\r\n]\+ \| stats")
            self.assertRegex(ko.stdout, r"[\r\n]- search = noop")

        with ksconf_cli:
            # Compare the same file to itself
            ko = ksconf_cli("diff", conf1, conf1)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_EQUAL)

        # Todo:  Only test this one on UNIX
        # For color mode (could work with ANY 2 different files)
        with ksconf_cli:
            ko = ksconf_cli("--force-color", "diff", conf1, conf2)
            # Keep this really simple for now
            self.assertRegex(ko.stdout, r"\x1b\[\d+m", "No TTY color markers found")
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)

    '''
    def test_diff_stdin(self):
        twd = TestWorkDir()
        conf1 = twd.write_file("savedsearches-1.conf", """
        [x]
        search = noop
        """)
        conf2 = twd.write_file("savedsearches-2.conf", r"""
        [x]
        search = tstats count where index=hippo by sourcetype, source \
        | stats values(source) by sourcetype
        """)
        try:
            _stdin = sys.stdin
            sys.stdin = open(conf2, "r")
            with ksconf_cli:
                ko = ksconf_cli("diff", conf1, "-")
                self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
        finally:
            sys.stdin = _stdin
        '''

    def test_diff_multiline(self):
        """ Force the generation of a multi-line value diff """
        twd = TestWorkDir()
        conf1 = twd.write_file("savedsearches-1.conf", r"""
        [indexed_event_counts_hourly]
        action.summary_index = 1
        action.summary_index.info = r3
        action.summary_index._name = summary_splunkidx
        cron_schedule = 29 * * * *
        description = Hourly report showing index event count and license usage data\
        All data is stored in a summary index for long term analysis.
        dispatch.earliest_time = 0
        enableSched = 1
        realtime_schedule = 0
        request.ui_dispatch_app = search
        request.ui_dispatch_view = search
        search = | tstats count as events, min(_time) as ts, max(_time) as te where _indextime>=`epoch_relative("-1h@h")` _indextime<=`epoch_relative("@h")` index=* OR index=_* NOT index=summary_splunkidx by index, sourcetype, host, source\
        | rename host as h, sourcetype as st, source as s, index as idx\
        | append\
            [ search earliest=-1h@h latest=@h index=_internal sourcetype=splunkd source=*license_usage* LicenseUsage "type=Usage"\
            | eval s=replace(s, "\\\\\\\\","\\")\
            | stats sum(b) as b by idx, st, h, s\
            | sort 0 - b ]\
        `indexed_event_count_hourly_filter`\
        | stats sum(b) as b, sum(events) as events, min(ts) as ts, max(te) as te by idx, st, h, s\
        | eval show_timestamps=if( ts<relative_time(now(), "-1h@h-1m") or te>relative_time(now(), "@h+1m"), "true", "false")\
        | eval ts=if(show_timestamps="true",ts, null())\
        | eval te=if(show_timestamps="true", te, null())\
        | fields - show_timestamps\
        | eval _time=relative_time(now(), "-1h@h")
        """)
        conf2 = twd.write_file("savedsearches-2.conf", r"""
        [indexed_event_counts_hourly]
        action.summary_index = 1
        action.summary_index.info = r4
        action.summary_index._name = summary_splunkidx
        cron_schedule = 29 * * * *
        description = Hourly report showing index event count and license usage data\
        All data is stored in a summary index for long term analysis.
        dispatch.earliest_time = -7d@h
        dispatch.latest_time = +21d@h
        enableSched = 1
        realtime_schedule = 0
        request.ui_dispatch_app = search
        request.ui_dispatch_view = search
        search = | tstats count as events, min(_time) as ts, max(_time) as te where _indextime>=`epoch_relative("-1h@h")` _indextime<=`epoch_relative("@h")` index=* OR index=_* NOT index=summary_splunkidx by index, sourcetype, host, source\
        | rename host as h, sourcetype as st, source as s, index as idx\
        | append\
            [ search earliest=-1h@h latest=@h index=_internal sourcetype=splunkd source=*license_usage* LicenseUsage "type=Usage"\
            | eval s=replace(s, "\\\\\\\\","\\")\
            | eval h=if(len(h)=0 OR isnull(h),"(SQUASHED)", h)\
            | eval s=if(len(s)=0 OR isnull(s),"(SQUASHED)", s)\
            | eval idx=if(len(idx)=0 OR isnull(idx), "(UNKNOWN)", idx) \
            | stats sum(b) as b by idx, st, h, s\
            | sort 0 - b ]\
        `indexed_event_count_hourly_filter`\
        | stats sum(b) as b, sum(events) as events, min(ts) as ts, max(te) as te by idx, st, h, s\
        | eval show_timestamps=if( ts<relative_time(now(), "-1h@h-1m") or te>relative_time(now(), "@h+1m"), "true", "false")\
        | eval ts=if(show_timestamps="true", ts, null())\
        | eval te=if(show_timestamps="true", te, null())\
        | fields - show_timestamps\
        | eval _time=relative_time(now(), "-1h@h")
        """)
        with ksconf_cli:
            ko = ksconf_cli("diff", conf1, conf2)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
            # Look for unchanged, added, and removed entries
            self.assertRegex(ko.stdout, r'[\r\n][ ]\s*\| rename host as h, sourcetype as st, source as s, index as idx')
            self.assertRegex(ko.stdout, r'[\r\n][+]\s*\| eval h=if[^[\r\n]+,"\(SQUASHED\)"')
            self.assertRegex(ko.stdout, r'[\r\n][-]\s*[^\r\n]+show_timestamps="true"')

    def test_diff_no_common(self):
        with ksconf_cli:
            ko = ksconf_cli("diff",  #"--comments",
                            static_data("savedsearches-sysdefault70.conf"),
                            static_data("inputs-ta-nix-default.conf"))
            #self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
            self.assertRegex(ko.stderr, "No common stanzas")




if __name__ == '__main__':  # pragma: no cover
    unittest.main()
