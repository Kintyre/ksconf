Contributing
============

Pull requests are greatly welcome! If you plan on contributing code back to the main ``ksconf``
repo, please follow the standard GitHub fork and pull-request work-flow. We also ask that you enable
a set of git hooks to help safeguard against avoidable issues.

Pre-commit hook
---------------

The ksconf project uses the pre-commit_ hook to enable the following checks:

-   Fixes trailing whitespace, EOF, and EOLs
-   Confirms python code compiles (AST)
-   Blocks the committing of large files and keys
-   Rebuilds the CLI docs. (Eventually to be replaced with an argparse Sphinx extension)
-   Confirms that all Unit test pass. (Currently this is the same tests also run by Travis CI, but
    since test complete in under 5 seconds, the run-everywhere approach seems appropriate for now.
    Eventually, the local testing will likely become a subset of the full test suite.)

..  note:: Multiple uses of pre-commit

    Be aware that the `ksconf repo`_ both uses pre-commit for validation of it's own content and it provides a pre-commit hook service definition for other repos.
    The first scenario is discussed in this section of the docs.
    The second scenario is for repositories housing Splunk apps to use :ref:`ksconf_cmd_check` and :ref:`ksconf_cmd_sort` as easy to use hooks against their own ``.conf`` files which is discussed further in :ref:`ksconf_pre_commit`.


Installing the pre-commit hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To run ensure you changes comply with the ksconf coding standards, please install and activate
pre-commit_.

Install:

..  code-block:: sh

    sudo pip install pre-commit

    # Register the pre-commit hooks (one time setup)
    cd ksconf
    pre-commit install --install-hooks

Install gitlint
~~~~~~~~~~~~~~~

Gitlint_ will check to ensure that commit messages are in compliance with the standard subject,
empty-line, body format. You can enable it with:

..  code-block:: sh

    gitlint install-hook



Refresh module listing
----------------------

After making changes to the module hierarchy or simply adding new commands, refresh the listing for
the autodoc extension by running the following command. Note that this may not remove old packages.

..  code-block:: sh

    sphinx-apidoc -o docs/source/ ksconf --force



Create a new subcommand
-----------------------

Checklist:


#.  Create a new module in ``ksconf.commands.<CMD>``.

    -   Create a new class derived from :class:`KsconfCmd`.
        You must at a minimum define the following methods:

        -   ``register_args()`` to setup any config parser inputs.
        -   ``run()`` which handles the actual execution of the command.
#.  Register a new entrypoint configuration in the ``setup_entrypoints.py`` script.
    Edit the ``_entry_points`` dictionary to add an entry for the new command.

        - Each entry must include command name, module, and implementation class.
#.  Create unit tests in ``test/test_cli_<CMD>.py``.
#.  Create documentation in ``docs/source/cmd_<CMD>.rst.``
    You'll want to build the docs locally to make sure everything looks correct.
    Part of the documentation is automatically generated from the argparse arguments defined in the ``register_args()`` method,
    but other other bits need to be spelled out explicitly.

When in doubt, it may be helpful to look back over history in git for other recently added commands and use that as an example.

..  include:: common
