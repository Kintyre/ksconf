..  _ksconf_cmd_merge:

ksconf merge
============

..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: merge
    :nodefault:


Examples
---------

Here is an elementary example that merges all ``props.conf`` file from *all* of your technology addons into a single output file:

..  code-block:: sh

    ksconf merge --target=all-ta-props.conf etc/apps/*TA*/{default,local}/props.conf

See an expanded version of this example here: :ref:`example_ta_idx_tier`
