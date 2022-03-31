..  _ksconf_cmd_package:


ksconf package
==============


.. argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: package
    :nodefault:


Variables
---------

The following variables are currently available for use during package building.
These are referenced using the ``{{var}}`` syntax.
See the implementation in :py:class:`~ksconf.package.AppVarMagic` if you'd like to contribute additional variables.

Supported Variables

    ==================  =========   ============================================================
    Variable            Source      Notes
    ==================  =========   ============================================================
    ``app_id``          app.conf    Get ``id`` from ``[package]`` in ``app.conf``.  This must be the app folder name for any app published to Splunkbase.
    ``build``           app.conf    Get ``build`` from ``[install]`` in ``app.conf``
    ``version``         app.conf    Get ``version`` from ``[launcher]`` in ``app.conf``
    ``git_tag``         git         Run ``git describe --tags --always --dirty``.  Common prefixes are removed such as ``v`` or ``release-`` from the tag name.
    ``git_last_rev``    git         Run ``git log -n1 --pretty=format:%h -- .``
    ``git_head``        git         Run ``git rev-parse --short HEAD``
    ``layers_list``     layers      List of unique ksconf layers used to build the app.  Layers are separated by an double underscores (``__``).  If no layers were used then an empty string is returned.
    ``layers_hash``     layers      Unique hash of unique ksconf layers used.  This is a truncated SHA256 of the ``layers_list`` variable.
    ==================  =========   ============================================================



Example
-------

..  code-block:: sh

    ksconf package -f my_app.tgz MyApp


A more realistic example where the version number in ``app.conf`` is managed by some external process, possibly a tool like ``bumpversion``.

..  code-block:: sh

    bumpversion minor
    ksconf package MyApp \
        --set-version={{git_tag}} \
        -f dist/my_app-{{version}}.tgz \
        --release-file=.artifact
    echo "Build complete, upload $(<.artifact) to SplunkBase"

This will output a message like: ``Build complete, upload dist/my_app-1.3.0.tgz to SplunkBase``

And of course this workflow could be further automated using Splunkbase API calls.


See also
--------

More sophisticated builds can be achieved using the :py:class:`~ksconf.builder.core.BuildManager`
