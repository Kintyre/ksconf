..  _ksconf_cmd_get-value:


ksconf get-value
================


.. argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: get-value
    :nodefault:



Example
^^^^^^^


Show the version of the Splunk AWS technology addon:

..  code-block:: sh

    ksconf get-value launcher version etc/apps/Splunk_TA_AWS/default/app.conf


Fetch the "live" (prefer local over default) search string called "Internal Server Errors" from my_app.
The search string will be saved to your text file without any additional metadata or continuation markers.

..  code-block:: sh

    ksconf merge $SPLUNK_HOME/etc/apps/my_app/{default,local}/savedsearches.conf \
    | ksconf get-value "Internal System Errors" search - -o errors_search.txt
