Changelog
=========

.. note:: Changes in master, but not released yet are marked as *DRAFT*.

Ksconf 0.6.x
------------

Add deployment as a Splunk app for simplicity and significant docs cleanup.

Release v0.6.1 (2019-02-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  (Trivial) Fixed some small issues with the Splunk App (online AppInspect)

Release v0.6.0 (2019-02-06)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Add initial support for building ksconf into a Splunk app.

   -  App contains a local copy of the docs, helpful for anyone who’s working offline.
   -  Credit to Sarah Larson for the ksconf logos.
   -  No ``ksconf`` functionality exposed to the Splunk UI at the moment.

-  Docs/Sphinx improvements (more coming)

   -  Begin work on cleaning up API docs.
   -  Started converting various document pages into reStructuredText for greatly improved docs.
   -  Improved PDF fonts and fixed a bunch of sphinx errors/warnings.

-  Refactored the install docs into 2 parts. With the new ability to install ksconf as a Splunk app
   it’s quite likely that most of the wonky corner cases will be less frequently needed, hence all
   the more exotic content was moved into the “Advanced Install Guide”, tidying things up.

Ksconf 0.5.x
------------

Add Python 3 support, new commands, support for external command plugins, tox and vagrant for testing.

Release v0.5.6 (2019-02-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixes and improvements to the ``filter`` command. Found issue with processing from stdin,
   inconsistency in some CLI arguments, and finished implementation for various output modes.
-  Add logo (fist attempt).

Release v0.5.5 (2019-01-28)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  New :ref:`ksconf_cmd_filter` command added for slicing up a conf file into smaller pieces. Think of this as
   GREP that’s stanza-aware. Can also whitelist or blacklist attributes, if desirable.
-  Expanded ``rest-export`` CLI capabilities to include a new ``–delete`` option, pretty-printing,
   and now supports stdin by allowing the user to explicitly set the file type using ``–conf``.
-  Refactored all CLI unittests for increased readability and long-term maintenance. Unit tests
   now can also be run individually as scripts from the command line.
-  Minor tweaks to the ``snapshot`` output format, v0.2. This feature is still highly experimental.

Release v0.5.4 (2019-01-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  New commands added:

   -  :ref:`ksconf_cmd_snapshot` will dump a set of configuration files to a JSON formatted file. This can be used
      used for incremental "snapshotting" of running Splunk apps to track changes overtime.
   -  :ref:`ksconf_cmd_rest-export` builds a series of custom ``curl`` commands that can be used to publish or update
      stanzas on a remote instance without file system access. This can be helpful when pushing
      configs to Splunk Cloud when all you have is REST (splunkd) access. This command is indented
      for interactive admin not batch operations.

-  Added the concept of command maturity. A listing is available by running ``ksconf --version``
-  Fix typo in ``KSCONF_DEBUG``.
-  Resolving some build issues.
-  Improved support for development/testing environments using Vagrant (fixes) and Docker (new).
   Thanks to Lars Jonsson for these enhancements.

Release v0.5.3 (2018-11-02)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixed bug where ``ksconf combine`` could incorrectly order directories on certain file systems
   (like ext4), effectively ignoring priorities. Repeated runs may resulted in undefined behavior.
   Solved by explicitly sorting input paths forcing processing to be done in lexicographical order.
-  Fixed more issues with handling files with BOM encodings. BOMs and encodings in general are NOT
   preserved by ksconf. If this is an issue for you, please add an enhancement issue.
-  Add Python 3.7 support
-  Expand install docs specifically for offline mode and some OS-specific notes.
-  Enable additional tracebacks for CLI debugging by setting ``KSCONF_DEBUG=1`` in the environment.

Release v0.5.2 (2018-08-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Expand CLI output for ``--help`` and ``--version``
-  Internal cleanup of CLI entry point module name. Now the ksconf CLI can be invoked as
   ``python -m ksconf``, you know, for anyone who’s into that sort of thing.
-  Minor docs and CI/testing improvements.

Release v0.5.1 (2018-06-28)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Support external ksconf command plugins through custom `entry_points`, allowing for others to
   develop their own custom extensions as needed.
-  Many internal changes: Refactoring of all CLI commands to use new entry_points as well as pave
   the way for future CLI unittest improvements.
-  Docs cleanup / improvements.

Release v0.5.0 (2018-06-26)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Python 3 support.
-  Many bug fixes and improvements resulting from wider testing.

Ksconf 0.4.x
------------

Ksconf 0.4.x switched to a modular code base, added build/release automation, PyPI package
registration (installation via ``pip install`` and, online docs.

Release v0.4.10 (2018-06-26)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Improve file handling to avoid “unclosed file” warnings. Impacted ``parse_conf()``,
   ``write_conf()``, and many unittest helpers.
-  Update badges to report on the master branch only. (No need to highlight failures on feature or
   bug-fix branches.)

Release v0.4.9 (2018-06-05)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Add some missing docs files

Release v0.4.8 (2018-06-05)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Massive cleanup of docs: revamped install guide, added ‘standalone’ install procedure and
   developer-focused docs. Updated license handling.
-  Updated docs configuration to dynamically pull in the ksconf version number.
-  Using the classic ‘read-the-docs’ Sphinx theme.
-  Added additional PyPi badges to README (GitHub home page).

Release v0.4.4-v0.4.1 (2018-06-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Deployment and install fixes (It’s difficult to troubleshoot/test without making a new release!)

Release v0.4.3 (2018-06-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Rename PyPI package ``kintyre-splunk-conf``
-  Add support for building a standalone executable (zipapp).
-  Revamp install docs and location
-  Add GitHub release for the standalone executable.

Release v0.4.2 (2018-06-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Add readthedocs.io support

Release v0.4.1 (2018-06-04)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Enable PyPI production package building

Release v0.4.0 (2018-05-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Refactor entire code base. Switched from monolithic all-in-one file to clean-cut modules.
-  Versioning is now discoverable via ``ksconf --version``, and controlled via git tags (via
   ``git describe --tags``).

Module layout
^^^^^^^^^^^^^

-  ``ksconf.conf.*`` - Configuration file parsing, writing, comparing, and so on
-  ``ksconf.util.*`` - Various helper functions
-  ``ksconf.archive`` - Support for uncompressing Splunk apps (tgz/zip files)
-  ``ksconf.vc.git`` - Version control support. Git is the only VC tool supported for now. (Possibly ever)
-  ``ksconf.commands.<CMD>`` - Modules for specific CLI functions. I may make this extendable, eventually.

Ksconf 0.3.x
------------

First public releases.

Release v0.3.2 (2018-04-24)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Add AppVeyor for Windows platform testing
-  Add codecov integration
-  Created ConfFileProxy.dump()

Release v0.3.1 (2018-04-21)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Setup automation via Travis CI
-  Add code coverage

Release v0.3.0 (2018-04-21)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Switched to semantic versioning.
-  0.3.0 feels representative of the code maturity.

Ksconf legacy releases
----------------------

Ksconf started in a private Kintyre repo. There are no official releases; all git history has been
rewritten.

Release legacy-v1.0.1 (2018-04-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixes to blacklist support and many enhancements to ``ksconf unarchive``.
-  Introduces parsing profiles.
-  Lots of bug fixes to various subcommands.
-  Added automatic detection of ‘subcommands’ for CLI documentation helper script.

Release legacy-v1.0.0 (2018-04-16)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  This is the first public release. First work began Nov 2017 (as a simple conf ‘sort’ tool,
   which was imported from yet another repo.) Version history was extracted/rewritten/preserved
   as much as possible.
-  Mostly stable features.
-  Unit test coverage over 85%
-  Includes pre-commit hook configuration (so that other repos can use this to run ``ksconf sort``
   and ``ksconf check`` against their conf files.
