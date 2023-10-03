..  _ksconf_cmd_merge:

ksconf merge
============

..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: merge
    :nodefault:

    --in-place: @after

    The ``--in-place`` option was added in v0.12.1.
    In earlier version of ksconf, and move forward, this same behavior can be accomplished by simply listing the target twice.
    Once as in the ``--target`` option, and then a second time as the first CONF file.


Examples
---------

Here is an elementary example that merges all ``props.conf`` file from *all* of your technology addons into a single output file:

..  code-block:: sh

    ksconf merge --target=all-ta-props.conf etc/apps/*TA*/{default,local}/props.conf

See an expanded version of this example here: :ref:`example_ta_idx_tier`
