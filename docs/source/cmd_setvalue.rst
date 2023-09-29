..  _ksconf_cmd_set-value:


ksconf set-value
================


.. argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: set-value
    :nodefault:



Example
^^^^^^^


Update build during CI/CD

..  code-block:: sh

    ksconf set-value build/default.app launcher version 1.1.2
    ksconf set-value build/default.app launcher build --value-type env GITHUB_RUN_NUMBER


Rewrite a saved search to match the new cooperate initiative to relabel all "CRITICAL" messages as "WHOOPSIES".

..  code-block:: sh

    ksconf get-value "Internal System Errors" search savedsearches.conf \
        | sed -re 's/CRITICAL/WHOOPSIES/g' \
        | ksconf set-value savedsearches.conf "Internal System Errors" search --value-type file -
