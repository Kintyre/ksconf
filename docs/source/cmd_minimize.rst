..  _ksconf_cmd_minimize:

ksconf minimize
***************

..  seealso:: See the :ref:`minimizing_files` for background on why this is important.


..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: minimize
    :nodefault:

    --output : @after
           This option can be used to *preview* the actual changes.
           Sometimes if ``--dry-run`` mode produces too much output, it's helpful to look at the
           actual minimized version of the file in concrete form (rather than a relative format, like
           a diff.)
           This may also be helpful in other workflows.

    --explode-default -E
           This mode will not only minimize the same stanza across multiple config files, it will
           also attempt to minimize any default values stored in the ``[default]`` or global stanza
           as well.
           For this to be effective, it's often necessary to include system-level defaults in the CONF list.
           For example, to trim out cruft in savedsearches.conf, make sure you add
           :file:`etc/system/default/savedsearches.conf` as an input.

    --k --preserve-key
           Sometimes it's desirable to keep default values explicitly in a local file even though it's
           technically redundant.  This is often true of boolean flags like ``disabled`` or input
           intervals.

           Note that if Splunk updates the stanzas itself, then your value may not longer be preserved.
           This is simply the way Splunk updates conf files.
           See :ref:`How Splunk write to conf files <splunk conf updates>` for more background.

Example usage
^^^^^^^^^^^^^

..  code-block:: sh

    cd Splunk_TA_nix
    cp default/inputs.conf local/inputs.conf

    # Edit 'disabled' and 'interval' settings in-place
    vi local/inputs.conf

    # Remove all the extra (unmodified) bits
    ksconf minimize --target=local/inputs.conf default/inputs.conf

Undoing a minimize
^^^^^^^^^^^^^^^^^^

You can use :ref:`ksconf_cmd_merge` to reverse the effect of minimize by running a command like so:


..  code-block:: sh

    ksconf merge default/inputs.conf local/inputs.conf

..  Confirm this works before advertising:  ksconf merge --target=local/inputs.conf default/inputs.conf local/inputs.conf
..  It's unclear if we allow --target to be the same file as one of the inputs....  Most likely this currently causes things to melt...but it shouldn't

Additional capabilities
^^^^^^^^^^^^^^^^^^^^^^^

For special cases, the ``--explode-default`` mode reduces duplication between entries in normal stanzas (as normal) and
then additionally reduces duplication between individual stanzas and default entries.
Typically you only need this mode if your dealing with a conf file that's been fully expanded to include all the layers,
which doesn't happen under normal circumstances.
This does happen anytime you download a stanza from a REST endpoint or munged together output from ``btool list``.
If you've ever done this with ``savedsearches.conf`` stanzas, you'll be painfully aware of how massive they are!
This is the exact use case that ``--explode-default`` was written for.

In such a case, it may be helpful to minimize against the full definition of *default*, which effectively requires looking at all the layers of default.
This includes all global app settings, and system-level settings.

There are limitations to this approach.

-   You have to manually list out all the layers.
    (Sometimes just pointing to the system-level defaults is good enough)
-   Minimize doesn't take namespace into account.
    This means ownership, sharing, and ACLs are ignored.

In many ways ``minimize`` mimics what Splunk does *every* time it updates a conf file, as discussed in :ref:`splunk conf updates`.
If you find yourself frequently needing the power of ``--explode-default``,
at some point a potentially better approach may be to simply post stanzas to the REST endpoint.
However, this typically does a good enough job, especially for offline scenarios.

Additionally, this command doesn't strictly require a bloated file.
For example, if ``disabled = 0`` is both a global default, and set on a per-stanza basis, that could be reduced too.
However, typically this isn't super helpful.


..  include:: common
