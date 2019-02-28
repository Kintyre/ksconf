..  _ksconf_cmd_rest-export:

ksconf rest-export
==================

..  deprecated:: 0.7.0

    You should consider using :ref:`ksconf_cmd_rest-publish` instead of this one.
    The only remaining valid use case for ``rest-export`` (this command) is for disconnected scenarios.
    In other words, if you need to push stanzas to a splunkd instance where you don't (and can't) install ``ksconf``,
    then this command may still be useful to you.
    In this case, ``ksconf rest-export`` can create a shell script that you can transfer to the correct network,
    and then run the shell script.
    But for **ALL** other use cases, the ``rest-publish`` command is superior.

..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: rest-export
    :nodefault:


..  warning:: For interactive use only

    This command is indented for manual admin workflows.  It's quite possible that shell escaping
    bugs exist that may allow full shell access if you put this into an automated workflow.  Evaluate
    the risks, review the code, and run as a least-privilege user, and be responsible.


Roadmap
--------

For now the assumption is that ``curl`` command will be used.  (Patches to support the Power Shell
``Invoke-WebRequest`` cmdlet would be greatly welcomed!)

Example
--------

.. code-block:: sh

    ksconf rest-export --output=apply_props.sh etc/app/Splunk_TA_aws/local/props.conf
