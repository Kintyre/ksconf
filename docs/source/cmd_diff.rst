ksconf diff
***********************

.. argparse::
   :module: ksconf.__main__
   :func: build_cli_parser
   :path: diff
   :nodefault:

   -o --output
         This is a local ``.conf`` file.

   CONF1 : @replace
         Also called ``a``
   CONF2
         Also called ``b``
