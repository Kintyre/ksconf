..  _ksconf_cmd_snapshot:

ksconf snapshot
===============

..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: snapshot
    :nodefault:


..  warning:: **Output NOT stable!**

    The output from this command hasn't really been tested in any kind of serious way for usability.
    Consider this a proof-of-concept.
    Anyone interested in this type of functionality should ref:`reach out <contact-us>` to discuss uses cases.


Example
--------

..  code-block:: sh

    ksconf snapshot --output=daily-$(date +%Y-%m-%d).json $SPLUNK_HOME/etc/app/
