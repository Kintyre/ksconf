#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
#
# Unlike the rest of ksconf, this file should remain Python 2.7 compatible
# This is just enough to gracefully report our presence in an unsupported
# version of Python, if we happen to get installed there.  Try really hard
# to avoid showing Python compiler errors as those are really confusing.

""" KSCONF - Ksconf Splunk CONFig tool

Optionally supports argcomplete for commandline argument (tab) completion.

Install & register with:

     pip install argcomplete
     activate-global-python-argcomplete  (in ~/.bashrc)

"""
from __future__ import absolute_import, unicode_literals

import sys

if sys.version_info < (3, 7):   # noqa
    # Can't actually import 'consts' because it loads 'enum'; so we cheat
    EXIT_CODE_BAD_PY_VERSION = 121
    sys.stderr.write(
        "ABORT!  ksconf cannot run here because it requires Python 3.7 or later!\n\n"
        "Check to see if you have multiple version of Python installed.\n"
        "If you need Python 2.7 or 3.6 support, consider downgrading to an earlier release.\n"
        "Releases 0.9.x support these older Python versions.\n\n"
        "If you installed this with pip, try running:\n\n"
        "   pip install -U 'kintyre-splunk-conf>=0.9,<=0.10'\n")
    sys.stderr.write("\nAdditional info\n"
                     "  Python:  {}  {}\n"
                     "  Ksconf:  {}\n".format(sys.executable, sys.version_info[:3], sys.argv[0]))
    sys.exit(EXIT_CODE_BAD_PY_VERSION)

from ksconf.cli import cli

if __name__ == '__main__':  # pragma: no cover
    cli()
