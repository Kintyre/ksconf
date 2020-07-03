..  _ksconf_cmd_promote:

ksconf promote
==============


..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: promote
    :nodefault:


..  warning::

    The promote command **moves** configuration settings between *SOURCE* and *TARGET* and therefore
    both files are updated.  This is unlike most other commands where only *TARGET* is modified.
    Using the ``--keep`` argument will prevent *SOURCE* from being updated.

Modes
-----

Promote has different modes:

    Batch mode
        Changes are applied automatically and the (now empty) source file is removed by default.
        The source file can be retained by using either the ``--keep`` or ``--keep-empty`` arguments, see descriptions above.

    Interactive mode
        Prompts the user to pick which stanzas and attributes to integrate.
        In practice, it's common that not all local changes will be ready to be promoted and committed at the same time.

        ..  hint:: This mode was inspired by :command:`git add --patch` command.

    Summary mode
        Shows the user a brief breakdown of what stanzas are available for promotion.
        This can be used to simply the use of the ``--stanza`` filtering options (automatic promotion) to show the names of stanzas available for promotion.
        Note that when ``--summary`` and ``--stanza`` are used at the same time, then the summary output will include any output not *already* matched by ``--stanza`` filter.

    Default
        If you haven’t specified either batch or interactive mode, you’ll be asked to pick one at startup.
        You'll be given the option to show a diff, apply all changes, or be prompted to keep or reject changes interactively.


Automated promotions
--------------------

Ksconf 0.7.8 added support for automatic stanza matching and promotion using a ``ksconf filter``-like CLI options.

Key features include:

    Automatic promotion of stanzas
        One or more named stanzas can be promoted automatically using the ``--stanza`` argument.
        This argument can be given multiple times to match multiples stanzas at once.
        In batch mode, only the named stanzas will be promoted;
        but in interactive mode, the named stanzas will be promoted first, and any content remaining to be promoted can be handled interactively.

    Matching mode
        Like with the ``ksconf filter`` command, multiple methods of matching are supported.
        This includes:  string matching (default), wildcard (or "glob") matching, and regular expressions.

    Inversion
        The ``--invert-match`` option allows for the selection to be inverted.
        In this mode, it's possible to select which stanzas should *not* be promoted.
        This can be used as a blocklist to prevent accidental promotions.



Safety checks
-------------

Moving content between files is a potentially risky operation.
Here are some of the safety mechanisms that ksconf has in place to prevent data loss.


..  tip::

    Pairing ksconf with a version control tool like :command:`git`, while not required, does provide another layer of protection against loss or corruption.
    If you promote and commit changes frequently, then the scope of potential loss is reduced.

..

    Syntax checking
        Strong syntax checking is enabled for both *SOURCE* and *TARGET* to prevent mistakes, such as dangling or duplicate stanzas,
        which could lead to even more corruption.

    File fingerprinting
        Various attributes of the *SOURCE* and *TARGET* files are captured at startup and compared again before any changes are written to disk.
        This reduces the possibility of a race-condition on a live Splunk system.
        This mostly impacts interactive mode because the session lasts longer.
        If this is a concern, run promote only when Splunk is offline.

    Same file check
        Attempts to promote content from a file to itself are prevented.
        While logically no one would want to do this, in practice having a clear error message saves time and confusion.

    Base name check
        The *SOURCE* and *TARGET* should share the same base name.
        In other words, trying to promote from :file:`inputs.conf` into :file:`props.conf` (due to a typo) will be prevented.
        This matters more in batch mode.
        In interactive mode, it should be pretty obvious that the type of entries don't make sense and therefore the user can simply exit without saving.

        For scripting purposes, there may be times where pushing changes between arbitrary-named files is helpful, so this check can be bypassed by using the ``--force`` argument.





.. note::

    Unfortunately, the unit testing coverage for the ``promote`` command is quite low.
    This is primarily because I haven't yet figured out how to handle unit testing for interactive CLI tools (as this is the only interactive command to date.)
    I'm also not sure how much the UI may change;
    Any assistance in this area would be greatly appreciated.


Examples
---------

A simple promotion looks like this.

    ..  code-block:: sh

            ksconf promote local/props.conf default/props.conf

This is equivalent to this minor shortcut.

    ..  code-block:: sh

            ksconf promote local/props.conf default

In this case, ksconf determines that ``default`` is a directory and therefore assumes that you want the same filename, ``props.conf`` in this case.

..  tip::  Using a directory as TARGET may seem like a trivial improvement, but in practice it greatly reduces accidental cross-promotion of content.  Therefore, we suggest its use.


Similarly, a shortcut for pushing between metadata files exists:

    ..  code-block:: sh

            ksconf promote metadata/local.meta metadata


A few example of automatic promotion of a named stanza:

    ..  code-block:: sh

            # Single stanzas
            ksconf promote local/savedsearches.conf default --stanza "My fancy search"

            # Wildcard promote all prod server alerts
            ksconf promote local/savedsearches.conf default --match wildcard --stanza "Server PRD* Alert"

            # Automatically promote everything except for one search:
            ksconf promote local/savedsearches.conf default --batch --invert-match --stanza "Local test"


Interactive mode
----------------

Keyboard shortcuts

    ===========     =======     ===========================================
    Key             Meaning     Description
    ===========     =======     ===========================================
    :kbd:`y`        Yes         Apply changes
    :kbd:`n`        No          Don't apply
    :kbd:`d`        Diff        Show the difference between the file or stanza.
    :kbd:`q`        Quit        Exit program.  Don't save changes.
    ===========     =======     ===========================================



Limitations
-----------

-   Currently, an attribute-level section has not be implemented.
    Entire stanzas are either kept local or promoted fully.
-   Interactive mode currently lacks "help".
    In the meantime, see the keyboard shortcuts listed above.
-   At present, comments in the *SOURCE* file will not be preserved.
-   If *SOURCE* or *TARGET* is modified externally while promote is running, the entire operation will be aborted, thus loosing any custom selections you made in interactive mode.
    This needs improvement.
-   There's currently no way to preserve certain local settings with some kind of "never-promote" flag.
    It's not uncommon to have some settings in  ``inputs.conf``, for example, that you never want to promote.
-   There is no *dry-run* mode supported.  Primarily, this is because it would only work for batch mode, and in interactive mode you explicitly see exactly what will be changed before anything is applied.
    (If you really need a dry-run for batch mode, use :ref:`ksconf_cmd_merge` to show the result of *TARGET* *SOURCE* combined.)
