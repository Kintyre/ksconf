.. _ksconf_cmd_xmlformat:

ksconf xml-format
=================


..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: xml-format
    :nodefault:

..  seealso:: Pre-commit hooks

    See :ref:`ksconf_pre_commit` for more information about how the ``xml-format`` command can be
    integrated in your git workflow.



Why is this important?
----------------------


TODO:  Note the alue of using ``<!CDATA[[ ]]>` blocks.

Value of consistent indentation.


To recursively format xml files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


..  code-block:: sh

    find . -path '*/data/ui/views/*.xml' -o -path '*/data/ui/nav/*.xml' | ksconf xml-format -
