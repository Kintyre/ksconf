#!/usr/bin/env python

# For coverage info, can be run with nose2, like so:
#  nose2 -s . -C

from __future__ import absolute_import, unicode_literals

import os
import sys
import unittest
from collections import OrderedDict
from copy import deepcopy
from functools import partial
from io import StringIO

import ksconf.ext.six as six

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.conf.delta import (DIFF_OP_DELETE, DIFF_OP_EQUAL, DIFF_OP_INSERT,
                               DIFF_OP_REPLACE, compare_cfgs,
                               summarize_cfg_diffs)
from ksconf.conf.parser import (DUP_EXCEPTION, DUP_MERGE, DUP_OVERWRITE,
                                GLOBAL_STANZA, PARSECONF_MID,
                                ConfParserException, DuplicateKeyException,
                                DuplicateStanzaException, parse_conf,
                                section_reader, write_conf)
from tests.cli_helper import TestWorkDir, parse_string


class ParserTestCase(unittest.TestCase):
    """ Test the parse_conf() Splunk .conf parser.  We should be at least as string as Splunk. """

    # List of test to add yet:

    # Todo:  Test comments in general...  Don't go too deep into this because we don't care too much, and eventually better comment support will break the API.
    # Todo:  Test trailing comments on stanzas
    # Todo:  Test trailing comments on key=value lines
    # Todo:  Test copy/deepcopy support:  Parse a string, copy, change original, confirm copy wasn't altered.

    def test_read_file(self):
        """ Confirm that parse_conf() works with an OS-level file. """
        d = {
            "stanza1": {"key1": "value1", "key2": "value2"},
            "stanza2": {"monkey": "banana", "dog": "cat"},
            "stanza3": {"key_with_no_value": ''},
        }
        tfile = StringIO()
        write_conf(tfile, d, sort=False)
        tfile.seek(0)
        d2 = parse_conf(tfile)
        self.assertDictEqual(d, d2)

    def test_multi_stanza(self):
        c = parse_string("""
        [stanza1]
        key1 = yes
        key2 = no
        [stanza2]
        key1 = no
        key2 = yes
        empty =
        """)
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assertEqual(c["stanza1"]["key2"], "no")
        self.assertEqual(c["stanza2"]["key1"], "no")
        self.assertEqual(c["stanza2"]["key2"], "yes")
        self.assertEqual(c["stanza2"]["empty"], "")

    def test_preserve_empty_stanza(self):
        c = parse_string("""
        [stanza1]
        key1 = yes
        key2 = no
        [stanza2]

        [stanza3]
        has_key = true
        """)
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assertTrue("stanza2" in c, "Must preserve empty stanza")
        self.assertEqual(len(c["stanza2"]), 0)
        self.assertEqual(c["stanza3"]["has_key"], "true")

    def test_preserve_empty_stanza_bug77(self):
        c = parse_string("""
        [capability::db_connect_create_connection]
        [capability::db_connect_read_connection]
        [capability::db_connect_update_connection]
        [capability::db_connect_delete_connection]
        """)
        self.assertTrue("capability::db_connect_create_connection" in c, "Must preserve empty stanza")
        self.assertTrue("capability::db_connect_delete_connection" in c, "Must preserve empty stanza")
        self.assertEqual(len(c), 4)

    def test_whitespace_keyvalue(self):
        c = parse_string("""
        [stanza1]
        key1=yes
        key2  =   no
        [stanza2]
         key1 =\tred
        key with spaces = not normal
        key2 = green   """)  # Trailing white space on key2
        self.assertEqual(c["stanza1"]["key1"], "yes")
        self.assertEqual(c["stanza1"]["key2"], "no")
        # XXX: This seems wrong...  we probably don't want to preserve whitespace in the key name.
        self.assertEqual(c["stanza2"][" key1"], "red")
        # Todo: Figure out what Splunk behavior is for trailing whitespace.  (For now, should pass)
        self.assertEqual(c["stanza2"]["key2"], "green   ")
        # Todo:  Does this ever happen...
        self.assertTrue(c["stanza2"]["key with spaces"])

    def test_missing_key(self):
        c = parse_string("""\
        [stanza1]
        key1=yes
        =  no
        [stanza2]
          = whoopsie
          """)
        self.assertEqual(c["stanza1"]["key1"], "yes")
        # Todo:  Review if this should throw an error or not...
        self.assertEqual(c["stanza1"][""], "no")
        self.assertEqual(c["stanza2"][""], "whoopsie")

    def test_inputs_with_BOM(self):
        twd = TestWorkDir()
        # "\\" in path due to non-raw string (Failing as of 87c5a11ca44; due to lack of BOM support)
        twd.write_file("inputs-bom.conf", b"\xef\xbb\xbf"
                                          b"[monitor://D:\\syslogs\\10.0.31.1]\n"
                                          b"disabled = false\n"
                                          b"sourcetype = cisco:asa\n"
                                          b"host_segment = 2\n"
                                          b"ignoreOlderThan = 7d\n")
        c = twd.read_conf("inputs-bom.conf")
        self.assertEqual(c[r"monitor://D:\syslogs\10.0.31.1"]["sourcetype"], "cisco:asa")

    def test_comments_with_BOM(self):
        # "\\" in path due to non-raw string (Failing as of 87c5a11ca44 if this is the FIRST line)
        twd = TestWorkDir()
        twd.write_file("comment-bom.conf", b"\xef\xbb\xbf# This is a comment\nx = 1")
        c = twd.read_conf("comment-bom.conf")
        self.assertTrue(c[GLOBAL_STANZA])

    def test_whitespace_stanza(self):
        c = parse_string("""
        [stanza 1]
        type = bool
        value = False
        [ stanza2]
        color = yellow
        [stanza 3 ]
        homework = no
         [stanza 4]
        pre_whitespace = weird
        [stanza 5]  """)
        self.assertEqual(c["stanza 1"]["type"], "bool")
        self.assertEqual(c[" stanza2"]["color"], "yellow")
        self.assertEqual(c["stanza 3 "]["homework"], "no")
        # This one fails....   need to confirm Splunk's built-in behavior....  Maybe this should fail on 'strict' mode?
        # self.assertEqual(c["stanza 4"]["pre_whitespace"], "weird")
        self.assertIn("stanza 5", c)

    def test_stanza_weird_chars(self):
        c = parse_string(r"""
        [source::...(/|\\)var(/|\\)log(/|\\)splunk(/|\\)*aws_sns*.log*]
        LINE_BREAKER=([\r\n]+)\d{4}-\d{2}-\d{2}
        sourcetype = aws:sns:alert:log
        priority = 1

        [source::...[/\\]var[/\\]log[/\\]splunk[/\\]s3util*.log*]
        sourcetype = aws:s3util:log
        priority = 10

        [My cool search [COOLNESS]]
        search = ...
        """)
        self.assertTrue(c[r"source::...(/|\\)var(/|\\)log(/|\\)splunk(/|\\)*aws_sns*.log*"])
        self.assertTrue(c[r"source::...[/\\]var[/\\]log[/\\]splunk[/\\]s3util*.log*"])
        self.assertTrue(c["My cool search [COOLNESS]"])

    def test_global_stanzs(self):
        c = parse_string("""
        animal = dog
        [jungle]
        animal = monkey
        [forest]
        animal = wolf
        """)  # Trailing white space on key2
        self.assertEqual(c[GLOBAL_STANZA]["animal"], "dog")
        self.assertEqual(c["jungle"]["animal"], "monkey")
        self.assertEqual(c["forest"]["animal"], "wolf")

    def test_bad_stanza(self):
        t1 = """
        [Errors in the last hour
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        t2 = """
        [Errors in the last hour
        ]
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        t3 = """
        Errors in the last hour]
        search = error OR failed OR severe OR ( sourcetype=access_* ( 404 OR 500 OR 503 ) )
        dispatch.earliest_time = -1h
        """
        # These SHOULD raise an error, even without strict=True
        with self.assertRaises(ConfParserException):
            parse_string(t1)

        with self.assertRaises(ConfParserException):
            parse_string(t2)

        with self.assertRaises(ConfParserException):
            parse_string(t3)

    def test_dup_keys(self):
        t = """
        [jungle]
        animal = monkey
        animal = snake
        [forest]
        animal = wolf
        """
        with self.assertRaises(DuplicateKeyException):
            parse_string(t, dup_key=DUP_EXCEPTION)

        c = parse_string(t, dup_key=DUP_MERGE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        self.assertEqual(c["forest"]["animal"], "wolf")

    def test_dup_stanzas(self):
        t = """
        [jungle]
        animal = monkey
        key2 = 01

        [forest]
        animal = wolf

        [jungle]
        animal = snake
        """
        with self.assertRaises(DuplicateStanzaException):
            parse_string(t, dup_stanza=DUP_EXCEPTION)

        c = parse_string(t, dup_stanza=DUP_MERGE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        self.assertEqual(c["jungle"]["key2"], "01")
        self.assertEqual(c["forest"]["animal"], "wolf")

        c = parse_string(t, dup_stanza=DUP_OVERWRITE)
        self.assertEqual(c["jungle"]["animal"], "snake")
        with self.assertRaises(KeyError):
            c["jungle"]["key2"]
        self.assertEqual(c["forest"]["animal"], "wolf")

    def test_strict_junk(self):
        t = """
        [stanza]
        key1 = an every-day value
        a random line of text that's not a key/value pair
        key2 = normalness
        """
        with self.assertRaises(ConfParserException):
            parse_string(t, strict=True)

    def test_unused_features(self):
        """ Make coverage stop complaining about stuff we don't use.  Remove later? """
        t = r"""
        [stanza]
        key1 = an every-day value
        KEY2 = normalness \
        another line
        """
        c = parse_string(t, strict=False, keys_lower=True)
        self.assertIn("key2", c["stanza"])
        self.assertEqual(len(c["stanza"]["key2"].split("\n")), 2)
        c = parse_string(t, strict=False, handle_conts=False)
        self.assertEqual(len(c["stanza"]["KEY2"].split("\n")), 1)
        self.assertNotIn("another line", c["stanza"]["KEY2"])

    def test_continuation(self):
        t = r"""
        [Sourcetype regex reuse]
        description = Determining similarities in sourcetypes based on which share the same EXTRACT regexes
        dispatch.earliest_time = 0
        display.general.type = statistics
        display.page.search.tab = statistics
        display.visualizations.show = 0
        search = | rest /servicesNS/-/-/configs/conf-props \
        | search eai:appName=* NOT title=source::* \
        | table title, EXTRACT-*, TIME_FORMAT, TIME_PREFIX, LINE_BREAKER, SHOULD_LINEMERGE, KV_MODE, sourcetype \
        | rename title as sourcetype \
        | untable sourcetype key value \
        | search key="EXTRACT-*" \
        | eval entry="[".sourcetype . "] " . key \
        | stats count values(entry) as entry by value \
        | where count>1
        """
        c = parse_string(t)
        self.assertEqual(len(c["Sourcetype regex reuse"]["search"].splitlines()), 9)

    def test_continuation_subsearch(self):
        """ Need to make sure that []"""
        t = r"""
        [Knowledge Object backup to CSV]
        description = Useful tool to export Knowledge Objects when (1) you don't have file-system \
        access, and (2) you only have Splunk Web access (no REST calls).
        search = | makeresults count=1 | \
        eval id="BACKUP-HEADER", now=now(), \
          title="BACKUP DESCRIPTION GOES HERE" \
        | append \
        [ rest splunk_server=local /servicesNS/-/-/data/ui/views ] \
        | append \
        [ rest splunk_server=local /servicesNS/-/-/configs/conf-macros ]
        request.ui_dispatch_view = search
        """
        c = parse_string(t)
        # If an empty global stanza is created, that's an implementation detail not important here.
        self.assertTrue(c["Knowledge Object backup to CSV"])
        self.assertNotIn(" rest splunk_server=local /servicesNS/-/-/configs/conf-macros ", c)
        self.assertEqual(len(c), 1, "Should only have 1 stanza")
        self.assertEqual(len(c["Knowledge Object backup to CSV"]["search"].splitlines()), 7)

    def test_splksysdfltjunk(self):
        # This is copied from Splunk's system/default/props.conf file.  (We are CERTAINLY more
        # picky than splunk when it comes to parsing these files.
        # Whoops, semi-colons aren't comments!
        t = r"""
        [sar]
        ; break on blanklines, clock-resets, or common headers attributes (/s, %, or alpha-)
        BREAK_ONLY_BEFORE = (?:^\s*$)|00:00:0|/s|%|[a-z]-
        MAX_EVENTS = 1000
        """
        c = parse_string(t, profile=PARSECONF_MID)
        self.assertEqual(c["sar"]["MAX_EVENTS"], "1000")

    def test_write_nonstr(self):
        """ Make sure that other python primitive types are written out correctly.  """
        # Note:  Types will not be preserved, but values should not be lost
        d = {"stanza": {"boolean1": True, "boolean2": False, "int1": 99, "int2": 0,
                        "none": None}}
        tfile = StringIO()
        write_conf(tfile, d)
        tfile.seek(0)
        d2 = parse_conf(tfile)
        st = d2["stanza"]
        self.assertEqual(st["boolean1"], "True")
        self.assertEqual(st["boolean2"], "False")
        self.assertEqual(st["int1"], "99")
        self.assertEqual(st["int2"], "0")
        self.assertEqual(st["none"], "")

    def test_write_doesnt_modify_dict(self):
        """ Ensure that calling write_conf(stream, conf) doesn't update conf in any way"""
        d = {
            GLOBAL_STANZA: {"a": 1, "b": 2},
            "my_sourcetype": {"SHOULD_LINEMERGE": "false"},
            "your_sourcetype": {"KV_MODE": "auto"},
        }
        d_copy = deepcopy(d)
        self.assertEqual(d_copy, d)
        write_conf(StringIO(), d)
        self.assertEqual(d_copy, d, "Dictionary sent to write_conf has been modified!")

    def test_write_unsorted(self):
        d = OrderedDict()
        d["stanza3"] = {"added": "first"}
        d["stanza2"] = {"added": "second"}
        d["a"] = {}
        tfile1 = StringIO()
        write_conf(tfile1, d, sort=False)
        # Ensure that stanza order is preserved
        sections = [s for s, _ in section_reader(tfile1.getvalue().splitlines()) if s]
        self.assertEqual(sections, ["stanza3", "stanza2", "a"])
        tfile2 = StringIO()
        write_conf(tfile2, d, sort=True)
        # Sorted version and non-sorted version SHOULD differ
        self.assertNotEqual(tfile1.getvalue(), tfile2.getvalue())


class ConfigDiffTestCase(unittest.TestCase):
    cfg_macros_1 = """
    [comment(1)]
    args = text
    definition = ""
    iseval = 1
    """

    cfg_props_imapsync_1 = r"""
    [other1]
    [imapsync]
    DATETIME_CONFIG =
    LINE_BREAKER = ([\r\n]+)(?:msg |PID|Writing|Folders |Host[12]|\+\+\++|Command|Log|Sending:|Modules version list)
    NO_BINARY_CHECK = true
    SHOULD_LINEMERGE = false
    TRUNCATE = 1000000
    category = Custom
    disabled = false
    pulldown_type = true
    """

    cfg_props_imapsync_2 = r"""
    [other2]

    [imapsync]
    LINE_BREAKER = ([\r\n]+)(?:msg |PID|Writing|Folders |Host[12]|\+\+\++|Command|Log|Sending:|Modules version list)
    TRUNCATE = 1000000
    NO_BINARY_CHECK = false
    category = Custom
    description = IMAP Sync tool
    pulldown_type = true
    """

    @staticmethod
    def find_op_by_location(diffs, type, **kwargs):
        for op in diffs:
            if op.location.type == type:
                match = True
                for (attr, value) in six.iteritems(kwargs):
                    if getattr(op.location, attr, None) != value:
                        match = False
                        break
                if match:
                    return op

    def test_compare_keys_props(self):
        c1 = parse_string(self.cfg_props_imapsync_1)
        c2 = parse_string(self.cfg_props_imapsync_2)
        diffs = compare_cfgs(c1, c2)

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="NO_BINARY_CHECK")
        self.assertEqual(op.tag, DIFF_OP_REPLACE)
        self.assertEqual(op.a, "true")
        self.assertEqual(op.b, "false")

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="LINE_BREAKER")
        self.assertEqual(op.tag, DIFF_OP_EQUAL)
        self.assertEqual(op.a, op.b)
        self.assertTrue(op.a.startswith(r"([\r\n]+)"))  # Don't bother to match the whole thing...

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="DATETIME_CONFIG")
        self.assertEqual(op.tag, DIFF_OP_DELETE)
        self.assertIsNotNone(op.a)
        self.assertIsNone(op.b)

        op = self.find_op_by_location(diffs, "key", stanza="imapsync", key="description")
        self.assertEqual(op.tag, DIFF_OP_INSERT)
        self.assertIsNone(op.a)
        self.assertIsNotNone(op.b)

    def test_imballanced_stanas(self):
        """ Imbalanced stanzas """
        a = parse_string("""
        [s0]
        _ = same
        [s1]
        a = 1
        b = 2
        [s3]
        y = 75
        [s4]
        z = 99
        """)
        b = parse_string("""
        [s0]
        _ = same
        [s1]
        a = 1
        c = 3
        [s2]
        x = 50
        [s4]
        zelda =
        """)
        delta = compare_cfgs(a, b)
        delta_search = partial(self.find_op_by_location, delta)

        op = delta_search("stanza", stanza="s0")
        self.assertEqual(op.tag, DIFF_OP_EQUAL)
        self.assertEqual(op.a, op.b)

        self.assertEqual(delta_search("key", stanza="s1", key="a").tag, DIFF_OP_EQUAL)
        self.assertEqual(delta_search("key", stanza="s1", key="b").tag, DIFF_OP_DELETE)
        self.assertEqual(delta_search("key", stanza="s1", key="c").tag, DIFF_OP_INSERT)

        self.assertEqual(delta_search("stanza", stanza="s2").tag, DIFF_OP_INSERT)
        self.assertEqual(delta_search("stanza", stanza="s3").tag, DIFF_OP_DELETE)
        self.assertEqual(delta_search("stanza", stanza="s4").tag, DIFF_OP_REPLACE)

    def test_empty_stanzas(self):
        """ Comparison should detect the different between empty and missing stanzas."""
        a = parse_string("""
        [common]
        a = 1
        b = 2

        [in_a1]
        live_in = a

        [in_a_only]
        """)
        b = parse_string("""
        [common]
        b = 2
        a = 1

        [in_b1]
        live_in = b

        [in_b_only]
        """)
        delta = compare_cfgs(a, b, preserve_empty=True)
        delta_search = partial(self.find_op_by_location, delta)
        self.assertEqual(delta_search("stanza", stanza="common").tag, DIFF_OP_EQUAL)
        self.assertEqual(delta_search("stanza", stanza="in_a_only").tag, DIFF_OP_DELETE)
        self.assertEqual(delta_search("stanza", stanza="in_b_only").tag, DIFF_OP_INSERT)

        op = delta_search("stanza", stanza="in_b1")
        self.assertEqual(op.tag, DIFF_OP_INSERT)
        self.assertEqual(op.b["live_in"], "b")

        op = delta_search("stanza", stanza="in_a1")
        self.assertEqual(op.tag, DIFF_OP_DELETE)
        self.assertEqual(op.a["live_in"], "a")

    def test_attribute_replace(self):
        props1 = parse_string(r"""
        [dhcp]
        EVAL-lease_end = lease_start+lease_duration
        EXTRACT-loglevel = ^\d+ (?<log_level>[^ ]+)
        EXTRACT-report-ack = ACK (?<dest_ip>[0-9.]+)/\d+ for (?<lease_duration>\d+)
        """)

        props2 = parse_string(r"""
        [dhcp]
        EVAL-lease_end = lease_start + lease_duration
        EXTRACT-loglevel = ^\d+ (?<log_level>[^ ]+)
        # Support IPv6
        EXTRACT-report-ack = ACK (?<dest_ip>[0-9A-Fa-f.:]+)/\d+ for (?<lease_duration>\d+)
        """)

        delta = compare_cfgs(props1, props2)
        delta_search = partial(self.find_op_by_location, delta)
        self.assertEqual(delta_search("key", stanza="dhcp", key="EXTRACT-loglevel").tag, DIFF_OP_EQUAL)

        lease_end = delta_search("key", stanza="dhcp", key="EVAL-lease_end")
        self.assertEqual(lease_end.tag, DIFF_OP_REPLACE)
        self.assertEqual(lease_end.a, "lease_start+lease_duration")
        self.assertEqual(lease_end.b, "lease_start + lease_duration")

        reportack = delta_search("key", stanza="dhcp", key="EXTRACT-report-ack")
        self.assertEqual(reportack.tag, DIFF_OP_REPLACE)
        self.assertIn(r"(?<dest_ip>[0-9A-Fa-f.:]+)", reportack.b)
        self.assertNotIn(r"(?<dest_ip>[0-9A-Fa-f.:]+)", reportack.a)

    def test_summarize_compare_results(self):
        c1 = parse_string(self.cfg_props_imapsync_1)
        c2 = parse_string(self.cfg_props_imapsync_2)
        diffs = compare_cfgs(c1, c2)
        output = StringIO()
        summarize_cfg_diffs(diffs, output)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
