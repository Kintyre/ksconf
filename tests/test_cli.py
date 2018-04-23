#!/usr/bin/env python

import unittest
from textwrap import dedent
from ksconf import *

import warnings
# Don't warn us about tempnam, we can't use tmpfile, we need an named filesystem object
warnings.filterwarnings("ignore", "tempnam is a potential security.*", RuntimeWarning)


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

def ksconf_cli(args, std_as="lines", tmpfile=os.tmpfile):
    """ Unfortunately, we have to redirect stdout/stderr while this runs, not
    very clean, but we try to make it as safe as possible.
    tmpfile:    os.tmpfile, or StringIO?
    """
    _stdout, _stderr = (sys.stdout, sys.stderr)
    try:
        # Capture all output written to stdout/stderr
        sys.stdout = tmpfile()
        sys.stderr = tmpfile()
        try:
            rc = cli(args, _unittest=True)
        except SystemExit, e:
            rc = e.message
        stdout = _stream_as(sys.stdout, std_as)
        stderr = _stream_as(sys.stderr, std_as)
    finally:
        (sys.stdout, sys.stderr) = _stdout, _stderr
    return KsconfOutput(rc, stdout, stderr)


class CliSimpleTestCase(unittest.TestCase):
    """ Test some very simple CLI features. """

    def test_help(self):
        out = ksconf_cli(["--help"], std_as="string")
        self.assertIn("Kintyre Splunk CONFig tool", out.stdout)
        self.assertIn("usage: ", out.stdout)


if __name__ == '__main__':
    unittest.main()
