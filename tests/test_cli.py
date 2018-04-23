#!/usr/bin/env python

import unittest
import tempfile
from textwrap import dedent
from ksconf import *

import warnings
# Don't warn us about tempnam, we can't use tmpfile, we need an named filesystem object
warnings.filterwarnings("ignore", "tempnam is a potential security.*", RuntimeWarning)


def static_data(path):
    # Assume "/" for path separation for simplicity; bunt handle OS independent.
    # Get paths to files under the 'tests/data/*' location
    parts = path.split("/")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "data", *parts))


def _stream_as(stream, as_):
    stream.seek(0)
    if as_ == "lines":
        return stream.readlines()
    elif as_ == "string":
        return stream.read()
    elif as_ == "stream":
        return stream


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
    tmpfile = os.tmpfile

    @staticmethod
    def _as_string(stream):
        stream.seek(0)
        return stream.read()

    def __call__(self, *args):
        self._last_args = args
        _stdout, _stderr = (sys.stdout, sys.stderr)
        rc = "INVALID"
        try:
            # Capture all output written to stdout/stderr
            temp_stdout = sys.stdout = self.tmpfile()
            temp_stderr = sys.stderr = self.tmpfile()
            try:
                rc = cli(args, _unittest=True)
            except SystemExit, e:
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
        if exc_type is not None:
            sys.stderr.write("Exception while running ksconf cli:  args={0!r}\n".format(self._last_args))
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
    def __init__(self, git_repo=False):
        if git_repo:
            self._path = tempfile.mkdtemp("-ksconftest-git")
            self.git("init")
        else:
            self._path = tempfile.mkdtemp("-ksconftest")

    def __del__(self):
        shutil.rmtree(self._path, ignore_errors=True)

    def git(self, *args):
        o = git_cmd(args, cwd=self._path)
        if o.returncode != 0:
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
        content = dedent(content)
        path = self.get_path(rel_path)
        self.makedir(None, path=os.path.dirname(path))
        with open(path, "w") as stream:
            stream.write(content)
        return path



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
        ksconf_cli("combine", "--target", default, default + ".d/*")
        cfg = parse_conf(twd.get_path("etc/apps/Splunk_TA_aws/default/props.conf"))
        self.assertIn("aws:config", cfg)
        self.assertEqual(cfg["aws:config"]["ANNOTATE_PUNCT"], "true")
        self.assertEqual(cfg["aws:config"]["EVAL-change_type"], '"configuration"')
        self.assertEqual(cfg["aws:config"]["TRUNCATE"], '9999999')
        nav_content = open(twd.get_path("etc/apps/Splunk_TA_aws/default/data/ui/nav/default.xml")).read()
        self.assertIn("My custom view", nav_content)


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
            self.assertRegexpMatches(ko.stdout, r"--- .*/savedsearches-1.conf \d{4}")
            self.assertRegexpMatches(ko.stdout, r"\+\+\+ .*/savedsearches-2.conf \d{4}")
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



class CliCheckTest(unittest.TestCase):

    def setUp(self):
        self.twd = twd = TestWorkDir()
        self.conf_bad = twd.write_file("badfile.conf", """
        # Invalid entry 'BAD_STANZA'
        [BAD_STANZA
        a = 1
        b = 2
        """)
        self.conf_good = twd.write_file("goodfile.conf", """
        c = 3
        [x]
        a = 1
        b = 2
        [y]
        a = 1
        """)

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

    def test_mixed_quiet(self):
        """ Make sure that if even a single file files, the exit code should be "BAD CONF" """
        with ksconf_cli:
            ko = ksconf_cli("check", self.conf_good, self.conf_bad)
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)


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
        from glob import glob
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
        files = glob(self.twd.get_path("*.conf"))
        with ksconf_cli:
            ko = ksconf_cli("sort", "-i", *self.all_confs )
            self.assertEqual(ko.returncode, EXIT_CODE_BAD_CONF_FILE)
            self.assertRegexpMatches(ko.stderr, r"Error [^\r\n]+? file [^\r\n]+?[/\\]badfile\.conf[^\r\n]+ \[BAD_STANZA")
            self.assertRegexpMatches(ko.stderr, r"Skipping blacklisted file [^ ]+[/\\]transforms\.conf")

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


class CliKsconfUnarchiveTestCase(unittest.TestCase):

    '''
    def __init__(self, *args, **kwargs):
        super(CliKsconfUnarchiveTestCase, self).__init__(*args, **kwargs)
        self._modsec_workdir = TestWorkDir(git_repo=True)
    '''

    def test_modsec_install_upgrade(self):
        twd = TestWorkDir(git_repo=True)
        self._modsec01_install_11(twd)
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_12.tgz")
        self._modsec01_upgrade(twd, "apps/modsecurity-add-on-for-splunk_14.tgz")

    def _modsec01_install_11(self, twd):
        """ Fresh app install a manual commit. """
        apps = twd.makedir("apps")
        tgz = static_data("apps/modsecurity-add-on-for-splunk_11.tgz")
        with ksconf_cli:
            kco = ksconf_cli("unarchive", tgz, "--dest", apps, "--git-mode=stage")
            self.assertIn("About to install", kco.stdout )
            self.assertIn("ModSecurity Add-on", kco.stdout, "Should display app name during install")
        twd.git("add", "apps/Splunk_TA_modsecurity")
        twd.git("commit", "-m", "Add custom file.")

    def _modsec01_upgrade(self, twd, app_tgz):
        """ Upgade app install with auto commit. """
        tgz = static_data(app_tgz)
        with ksconf_cli:
            kco = ksconf_cli("unarchive", tgz, "--dest", twd.get_path("apps"),
                             "--git-mode=commit", "--no-edit")
            self.assertIn("About to upgrade", kco.stdout)
            self.assertIn("ModSecurity Add-on", kco.stdout,
                          "Should display app name during install")



if __name__ == '__main__':
    unittest.main()
