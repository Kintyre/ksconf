ksconf diff
===========

.. topic:: Summary

   Compare settings differences between two .conf files
   ignoring spacing and sort order

.. _ksconf_cmd_diff:
.. argparse::
   :module: ksconf.__main__
   :func: build_cli_parser
   :path: diff
   :nodefault:

   -o --output
         This is a local ``.conf`` file.
