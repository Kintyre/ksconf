..  _ksconf_cmd_sort:

ksconf sort
===========

..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: sort
    :nodefault:


..  seealso:: Pre-commit hooks

    See :ref:`ksconf_pre_commit` for more information about how the ``sort`` command can be easily integrated in your git workflow.


Examples
^^^^^^^^

To recursively sort all files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


..  code-block:: sh

    find . -name '*.conf' | xargs ksconf sort -i
