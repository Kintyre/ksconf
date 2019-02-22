.. _ksconf_cmd_check:

ksconf check
============


..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: check
    :nodefault:


..  seealso:: Pre-commit hooks

    See :ref:`ksconf_pre_commit` for more information about how the ``check`` command can be easily
    integrated in your git workflow.


How 'check' differs from btool's validation
--------------------------------------------

Keep in mind that ksconf idea of *valid* is different than Splunk's.  Specifically,

 -  **Ksconf is more picky syntactically.**  Dangling stanzas and junk lines are picked up by
    ksconf in general (the 'check' command or others), but silently ignored Splunk.
 -  **Btool handles content validation.** The :command:`btool check` mode does a great job of check
    stanza names, attribute names, and values.  Btool does this well and ksconf tries to not repeat
    things that Splunk already does well.


.. _why_check:

Why is this important
----------------------

Can you spot the error in this :file:`props.conf`?

..  code-block:: text
    :linenos:

    [myapp:web:access]
    TIME_PREFIX = \[
    SHOULD_LINEMERGE = false
    category = Web
    REPORT-access = access-extractions

    [myapp:total:junk
    TRANSFORMS-drop = drop-all


That's right, line 7 contains the stanza ``myapp:total:junk`` that doesn't have a closing ``]``.
How Splunk handle this?  It ignores the broken stanza header completely and therefore ``TRANSFORMS-drop`` gets added
to the ``myapp:web:access`` sourcetype and very likely going to start loosing data.


Splunk also ignores entries like this:

::

    EVAL-bytes-(coalesce(bytes_in,0)+coalesce(bytes_out,0))

Of course here there's no ``=`` anywhere on the line, so Splunk just assumes it's junk and silently
ignores it.

..  tip::

    If you want to see how different this is.  Run ksconf check against the system default files:

    ..  code-block:: sh

        ksconf check --quiet $SPLUNK_HOME/etc/system/default/*.conf

    There's several files that ship with the core product that don't pass this level of validation.
