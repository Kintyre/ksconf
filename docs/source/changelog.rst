Changelog
=========

.. note:: Changes in master, but not released yet are marked as *DRAFT*.

Ksconf 0.8
----------

**Highlights:**

*  New command :ref:`ksconf_cmd_package` is designed for both Splunk developers and admins *  New module :py:mod:`ksconf.builder` helps build Splunk apps using a pipeline; or when external Python libraries are bundled into an app
*  Legit layer support with built-in layer filtering capabilities is available in several commands
*  Python 3!  Head's up: We'll be dropping support for Python 2 in an upcoming release

..  note::

   Come chat about ksconf on `GitHub discussions <https://github.com/Kintyre/ksconf/discussions>`__ even if it's to say we should use some other forum to stay in touch.

**What's new:**

-  The **new ksconf package command** supports the creation of Splunk app ``.spl`` files from a source directory.
   The ``package`` command can be used by admins to transfer apps around an organization, while keeping the ``local`` folder intact,
   or by a developer who wants ``local`` to be automatically merged into ``default``.
   The app version can be set based on the latest git tag by simply saying ``--set-version={{git_tag}}``.
-  The **ksconf.builder Python module** is a API-only first for ksconf!
   This build library allow caching of expensive deterministic build operations, and has out-of-the-box support for frequent build steps like adding Python modules locally using ``pip``.
   As the first feature with no CLI support, I'm exceeded to get input from the broader community on this approach.
   Of course this is just an experimental first release.
   As always, feedback welcome!
-  **Native support for layers!**
   It's official, layers are now a proper ksconf feature, not just an abstract concept that you could throw together yourself given enough time and effort.
   This does mean that ksconf has to be more opinionated, but the design supports switching layer methods,
   which can be extended over time to support new different strategies as they emerge and are embraced by the community.
   Supports layers filtering as a native feature.  This has always been technically possible, but awkward to implement yourself.
   Layer support is currently available in :ref:`ksconf_cmd_combine` and :ref:`ksconf_cmd_package` commands.
-  **Moving to Python 3 soon.**
   In preparation for the move to Python 3, I've added additional backport libraries to be installed when running Python 2.
   Support for Python 2 will be dropped in a future release, and anyone still on Splunk 7 who can't get a Python 3 environment will have to use an older version of ksconf.
   Also note that when jumping to Python 3, we will likely be requiring Python 3.6 or newer right out of the gate.  (This means dropping Python 2.7, 3.4 and 3.5 all at the same time.)
   Whoohoo for f-strings!
-  **CLI option abbreviation has been disabled.**
   This could be a breaking change for existing scripts.
   Hopefully no one was relying on this already, but in order to prevent long-term CLI consistency issues as new CLI arguments are added, this feature has been disabled for all version of Python.
   This feature is only available, and was enabled by default, starting in Python 3.5.
-  **Removed insensitive language.**
   Specifically the terms 'whitelist' and 'blacklist' have been replaced, where possible.
   Fortunately, these terms were not used in any CLI arguments, so there should be no user-facing changes as a result of this.
-  **Removed support for building a standalone executable (zipapp).**
   This packaging option was added in v0.4.3, and deprecated in v0.6.0 once the Splunk app install option became available.
   I'm pretty sure this won't be missed.


**API Changes**

-  NEW API :py:mod:`ksconf.builder`
   The documentation for this module needs work, and the whole API should be considered quite experimental.
   The easiest way to get started is to look at the :doc:`Build Example <build_example>`.

-  NEW Context manager :py:class:`~ksconf.conf.parser.update_conf`.
   This enables super easy conf editing in Python with just a few lines of code.
   See docs API docs for a usage example.

**Developer changes:**

-  Formatting via autopep8 and isort (enforced by pre-commit)
-  Better flake8 integration for bulk checking  (run via:  ``tox -e flake8,flake8-unittest``)

Ksconf v0.8.6 (2020-04-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~
-   Fixed ``install.py`` Splunk app CLI install helper script to support referencing a specific version of Python.  This is needed on Splunk 8.0 if you'd like to use Python 3 (or Splunk 8.1 if you want to use Python 2.7, but please don't.)
-   Updated docs regarding changes to the use of ``install.py`` and fixed a bunch of spelling mistakes and other minor doc/comment tweaks.
-   Fixed ASCII art issue.


Ksconf v0.8.5 (2020-04-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~
-   Fixed packaging issue where external dependencies were missing.
    This doesn't impact the Splunk package install, or anyone running Python 3.6 or later.

Ksconf v0.8.4 (2020-03-22)
~~~~~~~~~~~~~~~~~~~~~~~~~~

-  **CLI change**: Replaced short option for ``--allowlist`` to be ``-a``, before it was ``-w``.
   I assume this was left over early development where the argument was initial called ``--whitelist``, but at this point ``-w`` is just confusing.
   Normally, I'd keep ``-w`` for a period of time and issue a deprecation warning.
   However, given that 0.8.0 was released less than a week ago, and that ksconf package is an "alpha" feature,
   I'm going to make this change without prior warning.
-  Add some safety checks to the package command to check for app naming issues (where the app folder doesn't match ``[package] id`` value in ``app.conf``), and hidden files and directories.
-  Add new ``{{app_id}}`` variable that's usable with the ksconf package command.
-  Added a new optional argument to :py:func:`~ksconf.builder.steps.copy_files` called ``target`` for additional control over the destination path of artifacts copied into the build folder.
-  Minor tweak to unhandled exceptions.  The name of the exception class is now show, and may be helpful in some situations.
-  When using ``make_missing`` in :py:class:`~ksconf.conf.parser.update_conf`, missing directories will now be created too.
-  Additional fixes to the Ksconf for Splunk App ``build.py`` script:  Now explicitly creating a top-level ``ksconf`` folder.
   It's likely that this was the root cause of several other issues.


Ksconf v0.8.3 (2021-03-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixed bugs created by v0.8.2 (yanked on pypi)
-  Properly resolved issues with Splunk app building process.
-  Open issue uncovered where ``ksconf package`` can produce a tarball that's unusable by Splunkbase.

Ksconf v0.8.1 (2021-03-20)
~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixed some build issues with the Splunk app.  (The splunk app is now built with ``ksconf package`` and the ``ksconf.builder``)
-  Minor doc fix up; you know, the stuff typically found minutes after any new release :-)

Ksconf v0.8.0 (2021-03-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to the 0.8 summary above, 0.8.0 specifically includes the following changes:

-  Add automatic layer support.
   Currently the two supported layer schemes are (1) explicit layers (really this will ``disable`` automatic layer detection), and (2) the ``dir.d`` format which uses the ``default.d/##-layer-name`` style directory support, which we previously promoted in the docs, but never really *fully* supported in a native way.
   This new ``dir.d`` directory layout support also allows for multiple ``*.d`` folders in a single tree (so not just ``default.d``), and if your apps have different layer-points in different apps, it's all handled transparently.
-  Layer selection support was added to the ``combine`` command.
   This allows you to ``--include`` and ``--exclude`` layers as you see fit.
   See the docs for more details and examples of this new functionality.
   This works for both the new ``dir.d`` directories and the explicit layers, though moving to the ``dir.d`` format is highly encouraged.
-  New cheatsheet example:  Using ``ksconf package`` and ``splunk install app`` together.
-  Updated the combine behavior to optimize for the situation where there is only a single conf input file provided.
   This behavior leaves any ``.conf`` or ``.meta`` file untouched so there's no sorting/normalizing or banner.
   See `#64 <https://github.com/Kintyre/ksconf/issues/64>`__.
-  Eliminated an "unknown command" error when one of the ksconf python modules has a SyntaxError.
   The new behavior isn't perfect (you may still see "unrecognized arguments"), but overall it's still a step in the right direction.



Ksconf 0.7.x
------------

New functionality, massive documentation improvements, metadata support, and Splunk app install fixes.

Release v0.7.10 (2021-03-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixed bug where empty stanzas in the local file could result in deletion in default with ``ksconf promote``.
   Updated diff interface to improve handling of empty stanzas, but wider support is still needed across other commands; but this isn't a high priority.

Release v0.7.9 (2020-09-23)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  Fixed bug where empty stanzas could be removed from ``.conf`` files.
   This can be detrimental for ``capability::*`` entries in ``authorize.conf``, for example.
   A big thanks to nebffa for tracking down this bug!

Release v0.7.8 (2020-06-19)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   New automatic ``promote`` mode is now available using CLI arguments!
    This allows stanzas to be selected for promotion from the CLI in batch and interactive modes.
    This implementation borrows (and shares code) with the ``ksconf filter`` command so hopefully the CLI arguments look familiar.
    It's possible to promote a single stanza, a stanza wildcard, regex or invert the matching logic and promote everything except for the named stanza (blocklist).
    Right now ``--stanza`` is the only supporting matching mode, but more can be added as needed.
    A huge thanks to mthambipillai for providing a pull-request with an initial implementation of this feature!
-   Added a new summary output mode (``ksconf promote --summary``) that will provide a quick summary of what content could be promoted.
    This can be used along side the new ``--stanza`` filtering options to show the names of stanzas that can be promoted.
-   Replaced insensitive terminology with race-neutral terms.  Specifically the terms 'blacklist' and 'whitelist' have been replaced.
    NOTE:  This does *not* change any CLI attributes, but in a few cases the standard output terminology is slightly different.
    Also terminology in ``.conf`` files couldn't be updated as that's controlled by Splunk.
-   Fixed bug in the ``unarchive`` command where a ``locale`` folder was blocked as a ``local`` folder and where a nested ``default`` folder (nested under a Python package, for example) could get renamed if ``--default-dir`` was used, now only the top-most ``default`` folder is updated.
    Also fixed an unlikely bug triggered when ``default/app.conf`` is missing.
-   Fixed bug with ``minimize`` when the required ``--target`` argument is not given.  This now results in a reminder to the user rather than an unhandled exception.
-   Splunk app packaging fix.  Write access to the app was previously not granted due to a spelling mistake in the metadata file.

Release v0.7.7 (2020-03-05)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Added new ``--follow-symlink`` option to the ``combine`` command so that input directory structures with symbolic links can be treated the same as proper directories.
-   Corrected Windows issue where wildcard (glob) patterns weren't expanded by for ``check`` and ``sort``.  This is primarily a difference in how a proper shells (e.g., bash, csh, zsh) handle expansion natively vs CMD on Windows does not.  However, since this is typically transparently handled by many CLI tools, we'll follow suite.  (BTW, running ksconf from the GIT Bash prompt is a great alternative.)  Only the most minimalistic expansion rules will be available, (so don't expect ``{props,transforms,app}.conf`` to work anytime soon), but this should be good enough for most use cases.  Thanks to SID800 for reporting this bug.
-   Fixed issues with the ``unarchive`` command when ``git`` is not installed or an app is being unarchived (installed/upgrade) into a location not managed by Git.  Note that additional output is now enabled when the ``KSCONF_DEBUG`` environmental variable is set (in lieu of a proper verbose mode).  Bug report provided by SID800.
-   Enhanced ``ksconf --version`` output to include Git executable path and version information; as well as a platform dump.  (Helpful for future bug reporting.)
-   Added feature to disable the marker file (safety check) automatically created by the ``combine`` command for use in automated processing workflows.
-   Updated ``pre-commit`` documentation and sample configurations to use ``rev`` rather than ``sha`` as the means of identifying upstream tags or revisions.  Recent releases of ``pre-commit`` will warn you about this during each run.
-   Fixed a temporary file cleanup issue during certain in-place file replacement operations.  (If you found any unexpected ``*.tmp`` files, this could have been the cause.)


Release v0.7.6 (2019-08-15)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Fresh review and cleanup of all docs!  (A huge thank you to Brittany Barnett for this massive undertaking)
-   Fixed unhandled exception when encountering a global stanza in metadata files.
-   Expand some error messages, sanity checks, and added a new session token (``--session-key``) authentication option for ``rest-publish``.

Release v0.7.5 (2019-07-03)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Fixed a long-term bug where the diff output of a single-line attribute change was incorrectly represented in the textual output of 'ksconf diff' and the diff output in other commands.  This resolves a combination of bugs, the first half of which was fixed in 0.7.3.
-   Allow ``make_docs`` script to run on Windows, and other internal doc build process improvements.

Release v0.7.4 (2019-06-07)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Inline the ``six`` module to avoid elusive bootstrapping cases where the module couldn't be found.
    This primarily impacts ``pre-commit`` users.
    The ``ksconf.ext.*`` prefix is being used for this, and any other inlined third party modules we may need in the future.
-   Other minor docs fixes and internal non-visible changes.


Release v0.7.3 (2019-06-05)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Added the new :ref:`ksconf_cmd_xml-format` command.

    -   The ``ksconf xml-format`` command brings format consistency to your XML representations of Simple XML dashboards and navigation files by fixing indentation automatically adding ``<![CDATA[ ... ]]>`` blocks, as needed, to reduce the need for XML escaping, resulting in more readable source.
    -   Additionally, a new pre-commit hook named :ref:`ksconf-xml-format <ksconf_pre_commit>` was added to leverage this new functionality.  It looks specifically for xml views and navigation files based on path.  This may also include Advanced XML, which hasn't been tested;  So if you use Advanced XML, proceed with caution.
    -   Note that this adds ``lxml`` as a packaging dependency which is needed for pre-commit hooks, but not strictly required at run time for other ksconf commands.  This is NOT ideal, and may change in the future in attempts to keep ksconf as light-weight and standalone as possible.  One possible alternative is setting up a different repo for pre-commit hooks.  Python packaging and distribution tips welcome.

-   Fixed data loss bug in ``promote`` (interactive mode only) and improved some UI text and prompts.
-   Fixed colorization of ``ksconf diff`` output where certain lines failed to show up in the correct color.
-   Fixed bug where debug tracebacks didn't work correctly on Python 2.7.  (Enable using ``KSCONF_DEBUG=1``.)
-   Extended the output of ``ksconf --version`` to show the names and version of external modules, when present.
-   Improved some resource allocation in corner cases.
-   Tested with Splunk 7.3 (numeric similarity in version numbers is purely coincidental)

..  attention:: **API BREAKAGE**

    The ``DiffOp`` output values for ``DIFF_OP_INSERT`` and ``DIFF_OP_DELETE`` have been changed in a backwards-compatible breaking way.
    The values of ``a`` and ``b`` were previously reversed for these two operations, leading to some code confusion.


Release v0.7.2 (2019-03-22)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Fixed bug where ``filter`` would crash when doing stanza matching if global entries were present.  Global stanzas can be matched by searching for a stanza named ``default``.
-   Fixed broken ``pre-commit`` issue that occurred for the ``v0.7.1`` tag.  This also kept ``setup.py`` from working if the ``six`` module wasn't already installed.  Developers and pre-commit users were impacted.


Release v0.7.1 (2019-03-13)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Additional fixes for UTF-8 BOM files which appear to happen more frequently with ``local`` files on Windows.
    This time some additional unit tests were added so hopefully there are few regressions in the future.
-   Add the ``ignore-missing`` argument to :ref:`ksconf_cmd_merge` to prevent errors when input files are absent.
    This allows bashisms ``Some_App/{{default,local}}/savedsearches.conf`` to work without errors if the local or default file is missing.
-   Check for incorrect environment setup and suggest running sourcing :file:`setSplunkEnv` to get a working environment.
    See `#48 <https://github.com/Kintyre/ksconf/issues/48>`__ for more info.
-   Minor improvements to some internal error handling, packaging, docs, and troubleshooting code.

Release v0.7.0 (2019-02-27)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

..  attention:: For anyone who installed 0.6.x, we recommend a fresh install of the Splunk app due to packaging changes.  This shouldn't be an issue in the future.

*General changes:*

-   Added new :ref:`ksconf_cmd_rest-publish` command that supersedes the use of ``rest-export`` for nearly every use case.  Warning:  No unit-testing has been created for this command yet, due to technical hurdles.
-   Added :doc:`cheatsheet` to the docs.
-   Massive doc cleanup of hundreds of typos and many expanded/clarified sections.
-   Significant improvement to entrypoint handling and support for conditional inclusion of 3rd party libraries with sane behavior on import errors, and improved warnings.  This information is conveniently viewable to the user via ``ksconf --version``.
-   Refactored internal diff logic and added additional safeties and unit tests.  This includes improvements to TTY colorization which should avoid previous color leaks scenarios that were likely if unhandled exceptions occur.
-   New support for metadata handling.
-   CLI change for ``rest-export``:  The ``--user`` argument has been replaced with ``--owner`` to keep clean separation between the login account and object owners.  (The old argument is still accept for now.)

*Splunk app changes:*

-   Modified installation of python package installation.  In previous releases, various ``.dist-info`` folders were created with version-specific names leading to a mismatch of package versions after upgrade.
    For this reason, we suggest that anyone who previously installed 0.6.x should do a fresh install.
-   Changed Splunk app install script to ``install.py`` (it was ``bootstrap_bin.py``).  Hopefully this is more intuitive.
-   Added Windows support to ``install.py``.
-   Now includes the Splunk Python SDK.  Currently used for ``rest-publish`` but will eventually be used for additional functionally unique to the Splunk app.

Ksconf 0.6.x
------------

Add deployment as a Splunk app for simplicity and significant docs cleanup.


Release v0.6.2 (2019-02-09)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   Massive rewrite and restructuring of the docs.  Highlights include:

    -   Reference material has been moved out of the user manual into a different top-level section.
    -   Many new topics were added, such as

        -   :ref:`ksconf_ext_diff`
        -   :ref:`splunk conf updates`
        -   :ref:`configuration-layers`
        -   :ref:`What's so important about minimizing files? <minimizing_files>`

    -   A new approach for CLI documentation.  We're moving away from the **WALL OF TEXT** thing.
        (Yeah, it was really just the output from ``--help``).  That was limiting formatting,
        linking, and making the CLI output way too long.

-   Refreshed Splunk app icons.  Add missing alt icon.
-   Several minor internal cleanups.  Specifically the output of ``--version`` had a face lift.

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
   GREP that’s stanza-aware. Can also allow or block attributes, if desirable.
-  Expanded ``rest-export`` CLI capabilities to include a new ``--delete`` option, pretty-printing,
   and now supports stdin by allowing the user to explicitly set the file type using ``--conf``.
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
-  ``ksconf.archive`` - Support for decompressing Splunk apps (tgz/zip files)
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

-  Fixes to blocklist support and many enhancements to ``ksconf unarchive``.
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
