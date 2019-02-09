..  _ksconf_cmd_sort:

ksconf sort
===========

..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: sort
    :nodefault:



Examples
^^^^^^^^

To recursively sort all files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


..  code-block:: sh

    find . -name '*.conf' | xargs ksconf sort -i
