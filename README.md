# Kintyre's Splunk CONFiguration tool

[![Travis](https://img.shields.io/travis/Kintyre/ksconf/master.svg)](https://travis-ci.org/Kintyre/ksconf/builds)
[![PyPI](https://img.shields.io/pypi/v/kintyre-splunk-conf.svg)](https://pypi.org/project/kintyre-splunk-conf/)
[![codecov](https://codecov.io/gh/Kintyre/ksconf/branch/master/graph/badge.svg)](https://codecov.io/gh/Kintyre/ksconf)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)
[![Windows Build status](https://ci.appveyor.com/api/projects/status/rlbgstkpf17y8nxh/branch/master?svg=true)](https://ci.appveyor.com/project/lowell80/ksconf/branch/master)
[![Documentation Status](https://readthedocs.org/projects/ksconf/badge/?version=latest)](https://ksconf.readthedocs.io/en/latest/?badge=latest)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/kintyre-splunk-conf.svg)](https://pypi.org/project/kintyre-splunk-conf/)

![Ksconf logo][logo]

This utility handles a number of common Splunk app maintenance tasks in an installable python
package.  Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which splunk can't handle natively).


## Install

**Splunk:**

 1. Download and install [KSCONF App for Splunk](https://splunkbase.splunk.com/app/4383/)
 2. Run the command:  `splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/install.py`

**Python:**

    pip install kintyre-splunk-conf

**Confirm installation** with the following command:

    ksconf --help

## Resources

Docs:

  * [Official docs](https://ksconf.readthedocs.io/en/latest/) hosted via ReadTheDocs.io
  * [Command line reference](./docs/source/dyn/cli.rst)
  * [Installation docs](./docs/source/install.rst)
  * [Change log](./docs/source/changelog.rst)


Need help?

 * Ask questions on [GitHub](https://github.com/Kintyre/ksconf/issues/new?labels=question) or [Splunk Answers](https://answers.splunk.com/app/questions/4383.html)
 * Chat about [#ksconf](https://slack.com/app_redirect?channel=CDVT14KUN) on Splunk's [Slack](https://splunk-usergroups.slack.com) channel


Get involved:

 * [Report bugs](https://github.com/Kintyre/ksconf/issues/new?template=bug.md)
 * Review [known bugs](https://github.com/Kintyre/ksconf/labels/bug)
 * [Request new features](https://github.com/Kintyre/ksconf/issues/new?template=feature-request.md&labels=enhancement)
 * [Contribute code](./docs/source/devel.md)


Presentations:

  * [The joys and pitfalls of managing your Splunk deployment with Git](http://kintyre.rocks/70d87) Philly Splunk Meetup - June 6, 2018
  * [Managing Splunk Deployments With Git and KSCONF](https://youtu.be/-NIME9XRqlo)
    ([slides](https://kintyre.rocks/ksconf18)) Splunk .conf bsides talk - Oct 2, 2018


[logo]: docs/images/logo.png
