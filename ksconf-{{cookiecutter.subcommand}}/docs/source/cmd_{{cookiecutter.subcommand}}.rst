..  _ksconf_cmd_{{cookiecutter.subcommand}}:


ksconf fancy
============


.. argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: {{cookiecutter.subcommand}}
    :nodefault:



Example
-------

..  code-block:: sh

    ksconf {{cookiecutter.subcommand}} my.conf your.conf



*Add screenshot here*

To use ``ksconf {{cookiecutter.subcommand}}``, check out :ref:`ksconf_{{cookiecutter.subcommand}}_thing`.
