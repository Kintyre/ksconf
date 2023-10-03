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

    ksconf attr-get etc/apps/Splunk_TA_AWS/default/app.conf --stanza launcher --attribute version



Fetch the search string for the "Internal Server Errors" search in the from my_app.
The search is saved to a text file without any metadata or line continuation markers (trailing ```\\`` characters.)
Note that ``kconf merge`` is used here to ensure that the "live" version of the search is shown, so ``local`` will be used if present, otherwise ``default`` will be shown.

..  code-block:: sh

    ksconf merge $SPLUNK_HOME/etc/apps/my_app/{default,local}/savedsearches.conf \
    | ksconf attr-get - -s "Internal System Errors" -a search -o errors_search.txt
