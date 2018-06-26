#!/usr/bin/env python
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import sys
import tempfile
import unittest
from io import open, StringIO
from collections import namedtuple
from glob import glob
from subprocess import list2cmdline
from textwrap import dedent

import six

from ksconf.consts import *
from ksconf.cli import cli
from ksconf.util.file import file_hash
from ksconf.vc.git import git_cmd

from ksconf.conf.parser import parse_conf, write_conf, \
    GLOBAL_STANZA, PARSECONF_MID


def _debug_file(flag, fn):       # pragma: no cover
    """ Dump file contents with a message string to the output.  For quick'n'diry unittest
    debugging only """
    with open(fn) as fp:
         content = fp.read()
    length = len(content)
    hash = file_hash(fn)
    print("\n{flag} {fn}  len={length} hash={hash} \n{content}".format(**vars()))

def static_data(path):
    # Assume "/" for path separation for simplicity; bunt handle OS independent.
    # Get paths to files under the 'tests/data/*' location
    parts = path.split("/")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "data", *parts))

KsconfOutput = namedtuple("KsconfOutput", ["returncode", "stdout", "stderr"])

'''
# Let's try to avoid launching external processes (makes coverage more difficult, and so on)
def ksconf_exec(args):
    args = list(args)
    args.insert(0, "ksconf.py")
    from subprocess import call
    args = list(args)
    if True:    # Coverage enabled
        args = ["coverage", "run", "-a" ] + args
    rc = call(args)
    return KsconfOutput(rc, ...)
'''

class _KsconfCli():
    """ Unfortunately, we have to redirect stdout/stderr while this runs, not
    very clean, but we try to make it as safe as possible.
    tmpfile:    os.tmpfile, or StringIO?
    """

    @staticmethod
    def _as_string(stream):
        stream.seek(0)
        return stream.read()

    def __call__(self, *args):
        # In later version of Python (3.4), something like this could be considered:
        # from contextlib import redirect_stdout
        self._last_args = args
        _stdout, _stderr = (sys.stdout, sys.stderr)
        try:
            # Capture all output written to stdout/stderr
            temp_stdout = sys.stdout = StringIO()
            temp_stderr = sys.stderr = StringIO()
            try:
                rc = cli(args, _unittest=True)
            except SystemExit as e:
                if hasattr(e, "code"): # PY3
                    rc = e.code
                else:
                    rc = e.message
        finally:
            # This next step MUST be done!
            (sys.stdout, sys.stderr) = _stdout, _stderr
        stdout = self._as_string(temp_stdout)
        stderr = self._as_string(temp_stderr)
        output = KsconfOutput(rc, stdout, stderr)
        self._last_output = output
        return output

    def __enter__(self):
        self._last_args = None
        self._last_output = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Don't worry with coverage here.  It gets plenty of testing DURING unittest development ;-)
        if exc_type is not None:  # pragma: no cover
            sys.stderr.write("Exception while running: ksconf {0}\n".
                             format(list2cmdline(self._last_args)))
            ko = self._last_output
            if ko:
                if ko.stdout:
                    sys.stderr.write("STDOUT:\n{0}\n".format(ko.stdout))
                if ko.stderr:
                    sys.stderr.write("STDERR:\n{0}\n".format(ko.stderr))
            # Re-raise exception
            return False

ksconf_cli = _KsconfCli()



class TestWorkDir(object):
    encoding = "utf-8"
    def __init__(self, git_repo=False):
        if git_repo:
            self._path = tempfile.mkdtemp("-ksconftest-git")
            self.git("init")
        else:
            self._path = tempfile.mkdtemp("-ksconftest")

    def __del__(self):
        if "KSCONF_KEEP_TEST_FILES" in os.environ:
            return
        # This apparently isn't working...
        shutil.rmtree(self._path)

    def git(self, *args):
        o = git_cmd(args, cwd=self._path)
        if o.returncode != 0:       # pragma: no cover
            # Because, if we're using ksconf_cli, then we may be redirecting these...
            stderr = sys.__stderr__
            stderr.write("Git command 'git {0}' failed with exit code {1}\n{2}\n"
                         .format(" ".join(args), o.returncode, o.stderr))
            raise RuntimeError("Failed git command (return code {0})".format(o.returncode))

    def get_path(self, rel_path):
        # Always using unix/URL style paths internally.  But we want this to be OS agnostic
        rel_parts = rel_path.split("/")
        return os.path.join(self._path, *rel_parts)

    def makedir(self, rel_path, path=None):
        if path is None:
            path = self.get_path(rel_path)
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    def write_file(self, rel_path, content):
        path = self.get_path(rel_path)
        self.makedir(None, path=os.path.dirname(path))
        kw = {}
        if isinstance(content, bytes):
            kw["mode"] = "wb"
        else:
            kw["mode"] = "w"
            kw["encoding"] = self.encoding
            content = dedent(content)
        with open(path, **kw) as stream:
            stream.write(content)
        return path

    def read_file(self, rel_path, as_bytes=False):
        path = self.get_path(rel_path)
        kw = {}
        if as_bytes:
            kw["mode"] = "rb"
        else:
            kw["mode"] = "r"
            kw["encoding"] = self.encoding
        with open(path, **kw) as stream:
            content = stream.read()
        return content

    def write_conf(self, rel_path, conf):
        path = self.get_path(rel_path)
        self.makedir(None, path=os.path.dirname(path))
        write_conf(path, conf)
        return path

    def read_conf(self, rel_path, profile=PARSECONF_MID):
        path = self.get_path(rel_path)
        return parse_conf(path, profile=profile)

    def copy_static(self, static, rel_path):
        src = static_data(static)
        with open(src, "r", encoding=self.encoding) as stream:
            content = stream.read()
        return self.write_file(rel_path, content)


class CliSimpleTestCase(unittest.TestCase):
    """ Test some very simple CLI features. """

    def test_help(self):
        out = ksconf_cli("--help")
        self.assertIn("Kintyre Splunk CONFig tool", out.stdout)
        self.assertIn("usage: ", out.stdout)


class CliKsconfCombineTestCase(unittest.TestCase):

    def test_combine_3dir(self):
        twd = TestWorkDir()
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/10-upstream/props.conf", """
        [aws:config]
        SHOULD_LINEMERGE = false
        TRUNCATE = 8388608
        TIME_PREFIX = configurationItemCaptureTime"\s*:\s*"
        TIME_FORMAT = %Y-%m-%dT%H:%M:%S.%3NZ
        TZ = GMT
        MAX_TIMESTAMP_LOOKAHEAD = 28
        KV_MODE = json
        ANNOTATE_PUNCT = false

        FIELDALIAS-dest = resourceType AS dest
        FIELDALIAS-object = resourceId AS object
        FIELDALIAS-object_id = ARN AS object_id
        EVAL-change_type = "configuration"
        EVAL-dvc = "AWS Config"
        EVAL-status="success"
        LOOKUP-action= aws_config_action_lookup status AS configurationItemStatus OUTPUT action
        LOOKUP-object_category = aws_config_object_category_lookup type AS resourceType OUTPUT object_category

        # unify account ID field
        FIELDALIAS-aws-account-id = awsAccountId as aws_account_id
        FIELDALIAS-region-for-aws-config = awsRegion AS region
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/10-upstream/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)
        # In the future there will be a more efficient way to handle the global 'ANNOTATE_PUCT' scenario
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/20-corp/props.conf", """
        [aws:config]
        TZ = UTC
        # Corp want's punct to be enabled globally
        ANNOTATE_PUNCT = true
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/60-dept/props.conf", """
        [aws:config]
        # Our config is bigger than yours!
        TRUNCATE = 9999999
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/60-dept/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">

        <view name="My custom view" />
        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        <view name="search" default="false" label="Search" />

        </nav>
        """)
        default = twd.get_path("etc/apps/Splunk_TA_aws/default")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--target", default, default + ".d/*")
            cfg = parse_conf(twd.get_path("etc/apps/Splunk_TA_aws/default/props.conf"))
            self.assertIn("aws:config", cfg)
            self.assertEqual(cfg["aws:config"]["ANNOTATE_PUNCT"], "true")
            self.assertEqual(cfg["aws:config"]["EVAL-change_type"], '"configuration"')
            self.assertEqual(cfg["aws:config"]["TRUNCATE"], '9999999')
            nav_content = twd.read_file("etc/apps/Splunk_TA_aws/default/data/ui/nav/default.xml")
            self.assertIn("My custom view", nav_content)
        twd.write_conf("etc/apps/Splunk_TA_aws/default.d/99-theforce/props.conf", {
            "aws:config": {"TIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%6NZ"}
        })
        twd.write_file("etc/apps/Splunk_TA_aws/default.d/99-the-force/data/ui/nav/default.xml", """
        <nav search_view="search" color="#65A637">
        <view name="My custom view" />
        <view name="Inputs" default="true" label="Inputs" />
        <view name="Configuration" default="false" label="Configuration" />
        </nav>
        """)
        twd.write_file("etc/apps/Splunk_TA_aws/default/data/dead.conf", "# File to remove")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--dry-run", "--target", default, default + ".d/*")
            self.assertRegexpMatches(ko.stdout, r'[\r\n][-]\s*<view name="search"')
            self.assertRegexpMatches(ko.stdout, r"[\r\n][+]TIME_FORMAT = [^\r\n]+%6N")
        with ksconf_cli:
            ko = ksconf_cli("combine", "--target", default, default + ".d/*")

    def test_require_arg(self):
        with ksconf_cli:
            ko = ksconf_cli("combine", "source-dir")
            self.assertRegexpMatches(ko.stderr, "Must provide [^\r\n]+--target")


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
            self.assertRegexpMatches(ko.stdout, r"[\r\n]disabled = FALSE")

    def test_merge_dry_run(self):
        twd = TestWorkDir()
        conf1 = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        conf2 = twd.write_file("inputs2.conf", """
        [script://./bin/ps.sh]
        disabled = FALSE
        inverval = 97
        index = os_linux
        """)
        newfile = twd.get_path("input-new.conf")
        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile, "--dry-run")

            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            # Todo: Figure out if this should be a "+" or "-"....
            self.assertRegexpMatches(ko.stdout, r"[\r\n][+-]disabled = FALSE")

        with ksconf_cli:
            ko = ksconf_cli("merge", conf1, conf2, "--target", newfile)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegexpMatches(ko.stdout, r"^$")



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
            self.assertRegexpMatches(ko.stdout, r"^diff ", "Missing diff header line")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]--- [^\r\n]+?[/\\]savedsearches-1.conf\s+\d{4}-\d\d-\d\d")
            self.assertRegexpMatches(ko.stdout, r"\+\+\+ [^\r\n]+?[/\\]savedsearches-2.conf\s+\d{4}-\d\d-\d\d")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]\+ \| stats")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]- search = noop")

        with ksconf_cli:
            # Compare the same file to itself
            ko = ksconf_cli("diff", conf1, conf1)
            self.assertEqual(ko.returncode, EXIT_CODE_DIFF_EQUAL)

        # Todo:  Only test this one on UNIX
        # For color mode (could work with ANY 2 different files)
        with ksconf_cli:
            ko = ksconf_cli("--force-color", "diff", conf1, conf2)
            # Keep this really simple for now
            self.assertRegexpMatches(ko.stdout, r"\x1b\[\d+m", "No TTY color markers found")
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
        """ Force the generate of a multi-line value diff """
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
            self.assertRegexpMatches(ko.stdout, r'[\r\n][ ]\s*\| rename host as h, sourcetype as st, source as s, index as idx')
            self.assertRegexpMatches(ko.stdout, r'[\r\n][+]\s*\| eval h=if[^[\r\n]+,"\(SQUASHED\)"')
            self.assertRegexpMatches(ko.stdout, r'[\r\n][-]\s*[^\r\n]+show_timestamps="true"')

    def test_diff_no_common(self):
        with ksconf_cli:
            ko = ksconf_cli("diff", #"--comments",
                            static_data("savedsearches-sysdefault70.conf"),
                            static_data("inputs-ta-nix-default.conf"))
            #self.assertEqual(ko.returncode, EXIT_CODE_DIFF_CHANGE)
            self.assertRegexpMatches(ko.stderr, "No common stanzas")



class CliCheckTest(unittest.TestCase):

    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.conf_bad = twd.write_file("badfile.conf", """
        # Invalid entry 'BAD_STANZA'
        [BAD_STANZA
        a = 1
        b = 2
        """)
        self.conf_good = twd.write_conf("goodfile.conf", {
            GLOBAL_STANZA: {"c": 3},
            "x": {"a": 1, "b": 2},
            "y": {"a": 1}
        })

    def test_check_just_good(self):
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)

    def test_check_just_bad(self):
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegexpMatches(ko.stdout, r"\b1 files failed")
            self.assertRegexpMatches(ko.stderr, r"badfile\.conf:\s+[^:]+:\s+\[BAD_STANZA")

    def test_mixed(self):
        """ Make sure that if even a single file files, the exit code should be "BAD CONF" """
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good, self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_mixed_stdin(self):
        """ Make sure that if even a single file files, the exit code should be "BAD CONF" """
        try:
            _stdin = sys.stdin
            sys.stdin = StringIO("\n".join([self.conf_good, self.conf_bad]))
            with ksconf_cli:
                ko = ksconf_cli("check", "-")
                self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
        finally:
            sys.stdin = _stdin

    def test_mixed_quiet(self):
        """ Make sure that if even a single file files, the exit code should be "BAD CONF" """
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good, self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)

    def test_mixed_quiet_missing(self):
        """ Test with a missing file """
        with ksconf_cli:
            # Yes, this may seem silly, a fresh temp dir ensures this file doesn't actually exist
            fake_file = self.twd.get_path("not-a-real-file.conf")
            ko = ksconf_cli("check", self.conf_good, fake_file)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegexpMatches(ko.stderr, r"Skipping missing file: [^\r\n]+[/\\]not-a-real-file.conf")


class CliSortTest(unittest.TestCase):
    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.conf_bogus = twd.write_file("bogus.conf", """
        # Global comment 1
        global_entry1 = x
        global_entry2 = y
        # Global Comment 2

        [b]
        z = 1
        y = 2
        x = 3
        [a]
        x = 1
        y =2

        z=3
        """)
        self.conf_bad = twd.write_file("badfile.conf", """
        [my stanza]
        x = 3
        [BAD_STANZA
        a = 1
        b = 2
        [other]
        z = 9
        """)
        # This could eventually be a stanza-only sort with key-order preservation
        self.no_sort = twd.write_file("transforms.conf", r"""
        # KSCONF-NO-SORT
        [the-classic-header-nullqueue]
        REGEX = ^PalletId.*$
        DEST_KEY = queue
        FORMAT = nullQueue

        [assign_sourcetype_mytool_subservice]
        SOURCE_KEY = MetaData:Source
        REGEX = [/\\]([A-Za-z]+)\.txt(?:\.\d+)?(?:\.gz)?$
        DEST_KEY = MetaData:Sourcetype
        FORMAT = sourcetype::MyTool:Services:$1
        """)

        self.all_confs = glob(twd.get_path("*.conf"))

    def test_sort_inplace_returncodes(self):
        """ Inplace sorting long and short args """
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", self.conf_bogus)
            self.assertEqual(ko.returncode, EXIT_CODE_SORT_APPLIED)
            self.assertRegexpMatches(ko.stderr, "^Replaced file")
        # Sort the second time, no there should be NO updates
        with ksconf_cli:
            ko = ksconf_cli("sort", "--inplace", self.conf_bogus)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegexpMatches(ko.stderr, "^Nothing to update")

    ''' # Leaving this enabled makes too much noise...
    @unittest.expectedFailure
    def test_sort_glob(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        glob_pattern = self.twd.get_path("*.conf")
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", glob_pattern)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegexpMatches(ko.stderr, r"badfile\.conf")
    '''

    def test_sort_mixed(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", *self.all_confs )
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegexpMatches(ko.stderr, r"Error [^\r\n]+? file [^\r\n]+?[/\\]badfile\.conf[^\r\n]+ \[BAD_STANZA")
            self.assertRegexpMatches(ko.stderr, r"Skipping blacklisted file [^ ]+[/\\]transforms\.conf")

    def test_sort_stdout(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", self.conf_bogus, self.no_sort  )
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegexpMatches(ko.stdout, r"-----+ [^\r\n]+[/\\]bogus\.conf")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]-----+ [^\r\n]+[/\\]transforms\.conf")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]DEST_KEY = [^\r\n]+[\r\n]FORMAT =",
                                     "transforms.conf should be sorted even with KSCONF-NO-SORT directive for non-inplace mode")

    def test_sort_mixed_quiet(self):
        # Not yet implemented.  Currently relying on the shell to do this.
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", "--quiet", *self.all_confs)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegexpMatches(ko.stderr, r"Error [^\r\n]+?[/\\]badfile\.conf")
            self.assertNotRegexpMatches(ko.stderr, r"Skipping [^\r\n]+?[/\\]transforms\.conf")
            self.assertRegexpMatches(ko.stderr, r"[\r\n]Replaced file [^\r\n]+?\.conf")
        # No there should be NO output
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", "--quiet", self.conf_bogus, self.no_sort)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertNotRegexpMatches(ko.stderr, r"Error [^\r\n]+?\.conf")
            self.assertNotRegexpMatches(ko.stderr, r"[\r\n]Skipping [^\r\n]+?[/\\]transforms.conf")
            self.assertNotRegexpMatches(ko.stderr, r"[\r\n]Replaced file [^\r\n]+?\.conf")

    if not hasattr(unittest.TestCase, "assertNotRegexpMatches"):
        def assertNotRegex(self, text, unexpected_regex, msg=None):
            # Copied from standard library; Missing from Python 3.4.  Should probably find a
            # better way to support this in general, but for now only this set of test needs it.
            """Fail the test if the text matches the regular expression."""
            import re
            if isinstance(unexpected_regex, (str, bytes)):
                unexpected_regex = re.compile(unexpected_regex)
            match = unexpected_regex.search(text)
            if match:
                standardMsg = 'Regex matched: %r matches %r in %r' % (
                    text[match.start() : match.end()],
                    unexpected_regex.pattern,
                    text)
                # _formatMessage ensures the longMessage option is respected
                msg = self._formatMessage(msg, standardMsg)
                raise self.failureException(msg)
        assertNotRegexpMatches = assertNotRegex


class CliMinimizeTest(unittest.TestCase):

    def test_minimize_cp_inputs(self):
        """ Test typical usage:  copy default-> local, edit, minimize """
        twd = TestWorkDir()
        local = twd.copy_static("inputs-ta-nix-local.conf", "inputs.conf")
        default = static_data("inputs-ta-nix-default.conf")
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--dry-run", "--target", local, default)
            self.assertRegexpMatches(ko.stdout, "[\r\n][ ]\[script://\./bin/ps\.sh\]")
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
            self.assertRegexpMatches(ko.stdout, r"[\r\n]-disabled")
            self.assertRegexpMatches(ko.stdout, r"[\r\n]-enableSched")
        orig_size = os.stat(conf).st_size
        with ksconf_cli:
            ko = ksconf_cli("minimize", "--explode-default", "--target", conf, sysdefault)
            final_size = os.stat(conf).st_size
            self.assertTrue(orig_size > final_size)



dummy_config = {
    "stanza" : { "any_content": "will do" }
}

class CliPromoteTest(unittest.TestCase):

    def sample_data01(self):
        twd = TestWorkDir()
        self.conf_default = twd.write_file("default/savedsearches.conf", r"""
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
        self.conf_local = twd.write_file("local/savedsearches.conf", r"""
        [License usage trend by sourcetype]
        alert.track = 1
        display.statistics.show = 1
        request.ui_dispatch_app = kintyre
        search = | tstats sum(b) as bytes where index=summary_splunkidx by st, _time span=1h \
        | timechart span=1h sum(eval(bytes/1073741824)) as b by st \
        | foreach * [ eval "<<FIELD>>"=round('<<FIELD>>',3) ]
        """)
        return twd

    def assert_data01(self, twd):
        d = twd.read_conf("default/savedsearches.conf")
        stanza = d["License usage trend by sourcetype"]
        self.assertEqual(stanza["disabled"], "0")
        self.assertEqual(stanza["alert.track"], "1")
        self.assertTrue(len(stanza["search"].splitlines()) > 2)

    def test_promote_batch_simple_keep(self):
        twd = self.sample_data01()
        with ksconf_cli:
            ksconf_cli("promote", "--batch", "--keep-empty", self.conf_local, self.conf_default)
            self.assertEqual(os.stat(self.conf_local).st_size, 0)  # "Local file should be blanked")
            self.assert_data01(twd)
        del twd

    def test_promote_batch_simple(self):
        twd = self.sample_data01()
        with ksconf_cli:
            ksconf_cli("promote", "--batch", self.conf_local, self.conf_default)
            self.assertFalse(os.path.isfile(self.conf_local))  # "Local file should be blanked")
            self.assert_data01(twd)
        del twd

    def test_promote_to_dir(self):
        twd = self.sample_data01()
        with ksconf_cli:
            ksconf_cli("promote", "--batch", self.conf_local, twd.get_path("default"))
            self.assertTrue(os.path.isfile(self.conf_default), "Default file should be created.")
            self.assertFalse(os.path.isfile(self.conf_local), "Default file should be created.")
            self.assert_data01(twd)

    def test_promote_new_file(self):
        twd = TestWorkDir()
        dummy_local = twd.write_conf("local/dummy.conf", dummy_config)
        dummy_default = twd.get_path("default/dummy.conf")
        twd.makedir("default")
        with ksconf_cli:
            # Expect this to fail
            ko = ksconf_cli("promote", "--batch", dummy_local, dummy_default)
            self.assertEqual(ko.returncode, EXIT_CODE_SUCCESS)
            self.assertRegexpMatches(ko.stdout, "Moving source file [^\r\n]+ to the target")

    def test_promote_same_file_abrt(self):
        twd = TestWorkDir()
        dummy = twd.write_conf("dummy.conf", dummy_config)
        with ksconf_cli:
            # Expect this to fail
            ko = ksconf_cli("promote", "--batch", dummy, dummy)
            self.assertEqual(ko.returncode, EXIT_CODE_FAILED_SAFETY_CHECK)
            self.assertRegexpMatches(ko.stderr, "same file")

    '''
    def test_promote_simulate_ext_edit(self):
        # Not quite sure how to do this reliably....  May need to try in a loop?
        pass
    '''



class CliKsconfUnarchiveTestCase(unittest.TestCase):

    '''
    def __init__(self, *args, **kwargs):
        super(CliKsconfUnarchiveTestCase, self).__init__(*args, **kwargs)
        self._modsec_workdir = TestWorkDir(git_repo=True)
    '''

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
            self.assertIn("ModSecurity Add-on", kco.stdout, "Should display app name during install")
        twd.write_file(".gitignore", "*.bak")
        twd.git("add", "apps/Splunk_TA_modsecurity", ".gitignore")
        twd.git("commit", "-m", "Add custom file.")
        twd.write_file("Junk.bak", "# An ignored file.")

    def _modsec01_untracked_files(self, twd):
        twd.write_file("untracked_file", "content")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", static_data("apps/modsecurity-add-on-for-splunk_12.tgz"),
                             "--dest", twd.get_path("apps"), "--git-sanity-check=ignored",
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
        twd = TestWorkDir() # No git, keeping it as simple as possible (also, test that code path)
        zfile = static_data("apps/technology-add-on-for-rsa-securid_01.zip")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", zfile, "--dest", twd.makedir("apps"))
            self.assertIn("About to install", kco.stdout)
            self.assertIn("RSA Securid Splunk Addon", kco.stdout)
            self.assertRegexpMatches(kco.stdout, "without version control support")

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
                self.assertRegexpMatches(kco.stdout, "with git support")


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
