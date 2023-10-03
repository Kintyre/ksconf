..  _ksconf_cmd_attr-get:


ksconf attr-get
================


.. argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: attr-get
    :nodefault:



Example
^^^^^^^


Show the version of the Splunk AWS technology addon:

..  code-block:: sh

    ksconf attr-get launcher version etc/apps/Splunk_TA_AWS/default/app.conf


Fetch the "live" (prefer local over default) search string called "Internal Server Errors" from my_app.
The search string will be saved to your text file without any additional metadata or continuation markers.

..  code-block:: sh

    ksconf merge $SPLUNK_HOME/etc/apps/my_app/{default,local}/savedsearches.conf \
    | ksconf attr-get "Internal System Errors" search - -o errors_search.txt
