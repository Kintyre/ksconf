..  _ksconf_cmd_rest-export:

ksconf rest-export
==================

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
