# Changelog


## Ksconf 0.5.x

Add Python 3 support, external command plugins, tox and vagrant for testing.

### Release v0.5.3 (UNRELEASED)
 * Fixed more issues with handling files with BOM encodings.  BOMs and encodings in general are NOT
   preserved by ksconf.  If this is an issue for you, please add an enhancement issue.
 * Expand install docs specifically for offline mode and some OS-specific notes.
 * Add changelog for v0.5.2 (whoops)

### Release v0.5.2 (2018-08-13)
 * Expand CLI output for `--help` and `--version`
 * Internal cleanup of CLI entry point module name.  Now the ksconf CLI can be invoked as
   `python -m ksconf`, you know, for anyone who's into that sort of thing.
 * Minor docs and CI/testing improvements.

### Release v0.5.1 (2018-06-28)
 * Support external ksconf command plugins through custom 'entry_points', allowing for others to
   develop their own custom extensions as needed.
 * Many internal changes:  Refactoring of all CLI commands to use new entry_points as well as pave
   the way for future CLI unittest improvements.
 * Docs cleanup / improvements.

### Release v0.5.0 (2018-06-26)
 * Python 3 support.
 * Many bug fixes and improvements resulting from wider testing.


## Ksconf 0.4.x

Ksconf 0.4.x switched to a modular code base, added build/release automation, PyPI package
registration (installation via `pip install` and, online docs.

### Release v0.4.10 (2018-06-26)
 * Improve file handling to avoid "unclosed file" warnings.  Impacted `parse_conf()`,
  `write_conf()`, and many unittest helpers.
 * Update badges to report on the master branch only.  (No need to highlight failures on feature or
   bug-fix branches.)

### Release v0.4.9 (2018-06-05)
* Add some missing docs files

### Release v0.4.8 (2018-06-05)
 * Massive cleanup of docs: revamped install guide, added 'standalone' install procedure and
   developer-focused docs.  Updated license handling.
 * Updated docs configuration to dynamically pull in the ksconf version number.
 * Using the classic 'read-the-docs' Sphinx theme.
 * Added additional PyPi badges to README (GitHub home page).

### Release v0.4.4-v0.4.1 (2018-06-04)

* Deployment and install fixes  (It's difficult to troubleshoot/test without making a new release!)

### Release v0.4.3 (2018-06-04)
 * Rename PyPI package `kintyre-splunk-conf`
 * Add support for building a standalone executable (zipapp).
 * Revamp install docs and location
 * Add GitHub release for the standalone executable.

### Release v0.4.2 (2018-06-04)
 * Add readthedocs.io support

### Release v0.4.1 (2018-06-04)
 * Enable PyPI production package building

### Release v0.4.0 (2018-05-19)
 * Refactor entire code base.  Switched from monolithic all-in-one file to clean-cut modules.
 * Versioning is now discoverable via `ksconf --version`, and controlled via git tags (via
   `git describe --tags`).

#### Module layout

 * `ksconf.conf.*` - Configuration file parsing, writing, comparing, and so on
 * `ksconf.util.*` - Various helper functions
 * `ksconf.archive` - Support for uncompressing Splunk apps (tgz/zip files)
 * `ksconf.vc.git` - Version control support.  Git is the only VC tool supported for now. (Possibly ever)
 * `ksconf.commands.<CMD>` - Modules for specific CLI functions.  I may make this extendable, eventually.

## Ksconf 0.3.x

First public releases.

### Release v0.3.2 (2018-04-24)
 * Add AppVeyor for Windows platform testing
 * Add codecov integration
 * Created ConfFileProxy.dump()

### Release v0.3.1 (2018-04-21)
 * Setup automation via Travis CI
 * Add code coverage

### Release v0.3.0 (2018-04-21)
 * Switched to semantic versioning.
 * 0.3.0 feels representative of the code maturity.

## Ksconf legacy releases

Ksconf started in a private Kintyre repo.  There are no official releases; all git history has been
rewritten.

### Release legacy-v1.0.1 (2018-04-20)
 * Fixes to blacklist support and many enhancements to `ksconf unarchive`.
 * Introduces parsing profiles.
 * Lots of bug fixes to various subcommands.
 * Added automatic detection of 'subcommands' for CLI documentation helper script.

### Release legacy-v1.0.0 (2018-04-16)
 * This is the first public release.  First work began Nov 2017 (as a simple conf 'sort' tool,
   which was imported from yet another repo.)  Version history was extracted/rewritten/preserved
   as much as possible.
 * Mostly stable features.
 * Unit test coverage over 85%
 * Includes pre-commit hook configuration (so that other repos can use this to run `ksconf sort`
   and `ksconf check` against their conf files.

