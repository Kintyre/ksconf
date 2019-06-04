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

    This command requires the external ``lxml`` Python module
    This package was specifically selected (over the built-in 'xml.etree' interface) because it
    (1) support round-trip preservation of CDATA blocks, and
    (2) it is already ships with Splunk's embedded Python.

    This is an optional requirement, unless you want to use the ``xml-format`` command.
    However, due to packaging limitations and pre-commit hook support, install the python package will attempt to install lxml as well.
    Please :ref:`reach out <contact_us>` if this is causing issues for you; I'm looking into other options too.




Why is this important?
----------------------


TODO:  Note the value of using ``<!CDATA[[ ]]>`` blocks.

Value of consistent indentation.


To recursively format xml files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


..  code-block:: sh

    find . -path '*/data/ui/views/*.xml' -o -path '*/data/ui/nav/*.xml' | ksconf xml-format -
