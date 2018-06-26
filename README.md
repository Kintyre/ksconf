# Kintyre's Splunk CONFiguration tool

[![Travis](https://img.shields.io/travis/Kintyre/ksconf/master.svg)](https://travis-ci.org/Kintyre/ksconf/builds)
[![PyPI](https://img.shields.io/pypi/v/kintyre-splunk-conf.svg)](https://pypi.org/project/kintyre-splunk-conf/)
[![codecov](https://codecov.io/gh/Kintyre/ksconf/branch/master/graph/badge.svg)](https://codecov.io/gh/Kintyre/ksconf)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)
[![Windows Build status](https://ci.appveyor.com/api/projects/status/rlbgstkpf17y8nxh/branch/master?svg=true)](https://ci.appveyor.com/project/lowell80/ksconf/branch/master)
[![Documentation Status](https://readthedocs.org/projects/ksconf/badge/?version=latest)](https://ksconf.readthedocs.io/en/latest/?badge=latest)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kintyre-splunk-conf.svg)](https://pypi.org/project/kintyre-splunk-conf/)


This utility handles a number of common Splunk app maintenance tasks in an installable python
package.  Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which splunk can't handle natively).

Install with

    pip install kintyre-splunk-conf

See full install documentation in the [install](./docs/source/install.md) document.


Confirm installation with the following command:

    ksconf --help

Docs:

  * [Official docs](https://ksconf.readthedocs.io/en/latest/)  Hosted via ReadTheDocs.io
  * [Command line reference](./docs/source/cli.md)
  * [Installation docs](./docs/source/install.md)

Presentations:

  * [Managing Splunk Deployments With Git and KSCONF](http://kintyre.rocks/70d87) Philly Splunk Meetup - June 6, 2018
