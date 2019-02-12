..  _ksconf_cmd_minimize:

ksconf minimize
***************

..  seealso:: See the :ref:`minimizing_files` for background on why this is important.


..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: minimize
    :nodefault:

    --output : @after
           This option can be used to *preview* the actual changes.
           Sometimes if ``--dry-run`` mode produces too much output, it's helpful to look at the
           acutal minimized version of the file in concrete form (rather than a relative format, like
           a diff.  This may also be helpful in other workflows.

    --explode-default -E
           This mode will not only minimize the same stanza across multiple config files, it will
           also attempt to minimize any default values stored in the ``[default]`` or global stanza
           as well.
           For this to be effective, it's often necessary to include system default in the CONF list.
           For example, to trim out cruft in savedsearches.conf, make sure you add
           :file:`etc/system/default/savedsearches.conf` as an input.

    --k --preserve-key
           Sometimes it's desirable keep default values explicitly in a local file even though it's
           technically redundant.  This is often true of boolean flags like ``disabled`` or input
           intervals.

           Note that if Splunk updates the stanzas itself, then your value may not longer be preseved.
           This is simply the way Splunk updates conf files.
           See :ref:`How Splunk write to conf files <splunk conf updates>` for more backgound.

Example usage
^^^^^^^^^^^^^

..  code-block:: sh

    cd Splunk_TA_nix
    cp default/inputs.conf local/inputs.conf

    # Edit 'disabled' and 'interval' settings in-place
    vi local/inputs.conf

    # Remove all the extra (unmodified) bits
    ksconf minimize --target=local/inputs.conf default/inputs.conf


Additional capabilities
^^^^^^^^^^^^^^^^^^^^^^^

For special cases, the ``--explode-default`` mode reduces duplication between entries normal stanzas
and global/default entries.  If ``disabled = 0`` is a global default, it's technically safe to
remove that setting from individual stanzas.  But sometimes it's preferable to be explicit, and this
behavior may be too heavy-handed for general use so it's off by default.  Use this mode if you need
your conf file that's been fully-expanded.  (i.e., conf entries downloaded via REST, or the output
of "btool list").  This isn't perfect, since many apps push their settings into the global
namespace, but it can help.  In many ways this process mimics what Splunk does *every* time it
updates a conf file.  The difference being that Splunk always has the full context, for this command
to work most effectively, it really need to be given *all* the layers of default (system, app level,
and so on).  Also keep in mind that when ksconf load this formation, it isn't taking ACLs into
consideration (the individual conf files are not linked to their metadata counterparts) so your
results may vary from what a live Splunk system would do.  Just something to think about.
(Probably not a big deal since this is all on the fringes.)



..  include:: common
