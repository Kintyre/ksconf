..  _ksconf_cmd_attr-set:


ksconf attr-set
================


.. argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: attr-set
    :nodefault:



Example
^^^^^^^


Update build during CI/CD

..  code-block:: sh

    ksconf attr-set build/default.app launcher version 1.1.2
    ksconf attr-set build/default.app launcher build --value-type env GITHUB_RUN_NUMBER


Rewrite a saved search to match the new cooperate initiative to relabel all "CRITICAL" messages as "WHOOPSIES".

..  code-block:: sh

    ksconf attr-get "Internal System Errors" search savedsearches.conf \
        | sed -re 's/CRITICAL/WHOOPSIES/g' \
        | ksconf attr-set savedsearches.conf "Internal System Errors" search --value-type file -
