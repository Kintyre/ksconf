.. _ksconf_cmd_xml-format:

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


NOTE:  While it may work on other XML files, it hasn't been tested for other files, and therefore is not recommended as a general-purpose XML formatter.
Specific awareness of various Simple XML tags is baked into this product.

..  note::

    This command requires the external ``lxml`` Python module.

    This package was specifically selected (over the built-in 'xml.etree' interface) because it
    (1) supports round-trip preservation of CDATA blocks, and
    (2) already ships with Splunk's embedded Python.

    This is an optional requirement, unless you want to use the ``xml-format`` command.

    As of v0.12.0, this is not longer installed by the ``ksconf`` package.
    However, if you are using pre-commit hooks from the `ksconf-pre-commit repo`_ for the ``ksconf-xml-format`` hook.



Why is this important?
----------------------


TODO:  Note the value of using ``<!CDATA[[ ]]>`` blocks.

Value of consistent indentation.


To recursively format xml files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


..  code-block:: sh

    find . -path '*/data/ui/views/*.xml' -o -path '*/data/ui/nav/*.xml' | ksconf xml-format -
