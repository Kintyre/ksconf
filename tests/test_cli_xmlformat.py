#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals

import os
import platform
import re
import sys
import unittest
from io import StringIO

# Allow interactive execution from CLI,  cd tests; ./test_cli.py
if __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksconf.consts import EXIT_CODE_BAD_CONF_FILE, EXIT_CODE_FORMAT_APPLIED, EXIT_CODE_SUCCESS
from tests.cli_helper import FakeStdin, TestWorkDir, ksconf_cli

# Something weird with LXML and PYPY:
#   bBaseException.__new__(XMLSyntaxError) is not safe, use XMLSyntaxError.__new__()
# PyPy support is low priority, just skipping on PYPY for now
PYPY = platform.python_implementation() == "PyPy"
WIN = sys.platform == "win32"


class CliXmlFormatTest(unittest.TestCase):

    sample1 = """\
    <?xml version="1.0" encoding="utf8"?>
    <form>
      <label>File Transfer Details</label>
      <init>
        <set token="form.drilldown">*</set>
      </init>
      <search id="ftp">
       <query><![CDATA[
    index=main sourcetype=ftp
    | table _time host user action directory filename size
    | eval size=size/1024
    ]]>
        </query>
        <earliest>$tp.earliest$</earliest>
        <latest>$tp.latest$</latest>
        <sampleRatio>1</sampleRatio>
      </search>
    <row>
      <panel>
          <title>FTP transactions</title>
          <input type="text" token="drilldown">
            <label>Post filter</label>
            <default>*</default>
          </input>
          <table>
            <search base="ftp">
              <query> | search $drilldown$</query>
            </search>
            <option name="count">20</option>
            <option name="percentagesRow">false</option>
            <option name="refresh.display">preview</option>
            <format type="number" field="size">
              <option name="precision">1</option>
              <option name="unit">kb</option>
            </format>
          </table>
        </panel>
      </row>
    </form>
    """

    sample2 = """<form><label>Transfer Details</label><init><set
    token="form.drilldown">*</set></init><search id="ftp"><query><![CDATA[
    index=main sourcetype=ftp
    | table _time host user action directory filename size
    | eval size=size/1024
    | where size>100
    ]]></query><earliest>$tp.earliest$</earliest><latest>$tp.latest$</latest>
    <sampleRatio>1</sampleRatio></search></form>
    """

    sample3 = """\
    <form>
       <label>Delivery Transfer Details</label>
       <init>
          <set token="form.drilldown">*</set>
       </init>
       <search id="ftp">
          <query>index=main sourcetype=ftp</query>
          <earliest>$tp.earliest$</earliest>
          <latest></latest>
          <sampleRatio>1</sampleRatio>
       </search>
    </form>
    """

    def setUp(self):
        self.twd = TestWorkDir()

    def cdata_regex(self, content=".*?", escape_content=False):
        # XXX PY36+: Switch to f-string, drop F841
        prefix = re.escape("<![CDATA[")  # noqa: F841
        suffix = re.escape("]]>")  # noqa: F841
        if escape_content:
            content = re.escape(content)
        return r"(?ms){prefix}.*?{content}.*?{suffix}".format(**vars())

    @unittest.skipIf(PYPY, "Skipping PyPy for XML exceptions")
    def test_broken_xml(self):
        f = self.twd.write_file("bad_view.xml", """
        <view>
        </dashboard>""")
        with ksconf_cli:
            ko = ksconf_cli("xml-format", f)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegex(ko.stdout, r"\b1 files failed")

    def test_no_indent(self):
        sample = self.twd.write_file("sample.xml", self.sample2)
        with ksconf_cli:
            ko = ksconf_cli("xml-format", sample)
            self.assertEqual(ko.returncode, EXIT_CODE_FORMAT_APPLIED)
            self.assertRegex(ko.stderr, r"Replaced file [^\r\n]+sample.xml")

        r'''   unicode vs str issue occurring here -->

        # Format again. Make sure there's no new changes
        with ksconf_cli:
            ko = ksconf_cli("xml-format", sample)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            #self.assertRegex(ko.stderr, r"1 file[^\r\n]+\salready formatted")
        '''

    @unittest.skipIf(PYPY, "Skipping PyPy for XML exceptions")
    def test_mixed_stdin(self):
        """ Make sure that if even a single file fails the exit code is correct. """
        sample1 = self.twd.write_file("sample.xml", self.sample1)
        bad1 = self.twd.write_file("sample.xml", "<view>truncated ...")
        instream = StringIO("\n".join([bad1, sample1]))
        with FakeStdin(instream):
            with ksconf_cli:
                ko = ksconf_cli("xml-format", "-")
                self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_missing(self):
        """ Test with a missing file """
        with ksconf_cli:
            # Yes, this may seem silly, a fresh temp dir ensures this file doesn't actually exist
            fake_file = self.twd.get_path("not-a-real-file.xml")
            ko = ksconf_cli("xml-format", fake_file)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stderr, r"Skipping missing file: [^\r\n]+[/\\]not-a-real-file.xml")

    @unittest.skipIf(WIN, "Skip due to EOL issues not yet resolved")
    def test_already_sorted(self):
        sample = self.twd.write_file("sample.xml", self.sample3)
        with ksconf_cli:
            ko = ksconf_cli("xml-format", sample)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegex(ko.stderr, r"Already formatted [^\r\n]+[/\\]sample\.xml")

    def test_promote_to_CDATA(self):
        sample = self.twd.write_file("sample.xml", r"""
        <form>
           <search id="ftp">
              <query>index=main sourcetype=ftp | rex "^\S+ \S+ (?&lt;user&gt;\S+)"
              | stats count by user</query>
              <earliest>$tp.earliest$</earliest>
              <latest></latest>
              <sampleRatio>1</sampleRatio>
           </search>
        </form>
        """)
        with ksconf_cli:
            ko = ksconf_cli("xml-format", sample)
            self.assertEqual(ko.returncode, EXIT_CODE_FORMAT_APPLIED)
            sample_out = self.twd.read_file("sample.xml")
            self.assertRegex(sample_out, self.cdata_regex(r"(?<user>\S+)", True))

    def test_preserve_CDATA(self):
        """ <![CDATA[]]> blocks should be preserved, even if there's no special characters. """
        sample = self.twd.write_file("sample.xml", self.sample1)
        with ksconf_cli:
            ko = ksconf_cli("xml-format", sample)
            self.assertEqual(ko.returncode, EXIT_CODE_FORMAT_APPLIED)
            sample_out = self.twd.read_file("sample.xml")
            # Must STILL contain CDATA after the run
            self.assertRegex(sample_out, self.cdata_regex())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
