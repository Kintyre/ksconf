..  _ksconf_cmd_rest-publish:

ksconf rest-publish
===================

..  note::

    This command effectively replaces :ref:`ksconf_cmd_rest-export` for nearly all use cases.
    The only thing that ``rest-publish`` can't do that ``rest-export`` can, is handle a disconnected scenario.
    But for **ALL** other use cases, the ``rest-publish`` (this command) command is far superior.

..  note:: This commands requires the Splunk Python SDK, which is automatically bundled with the *Splunk app for KSCONF*.


..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: rest-publish
    :nodefault:

    -m, --meta:
        Note that ``mtime`` is ignored as that attribute is updated automatically every time a change occurs.
        There is no known way to work around this without file system access.

--------



Examples
---------

A simple example:

.. code-block:: sh

    ksconf rest-publish etc/app/Splunk_TA_aws/local/props.conf \
        --user admin --password secret --app Splunk_TA_aws --owner nobody --sharing global


This command also supports replaying metdata like ACLs:

.. code-block:: sh

    ksconf rest-publish etc/app/Splunk_TA_aws/local/props.conf \
        --meta etc/app/Splunk_TA_aws/metdata/local.meta \
        --user admin --password secret --app Splunk_TA_aws
