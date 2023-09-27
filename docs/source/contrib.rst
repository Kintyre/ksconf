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
-   Rebuilds the dynamic portions of the docs related to the CLI.
-   Confirms that all unit tests pass. (Currently, this is the same test run by Travis CI, but
    since tests complete in under 5 seconds, the run-everywhere approach seems appropriate for now.
    Eventually, the local testing will likely become a subset of the full test suite.)

..  note:: Multiple uses of pre-commit

    Be aware, that the `ksconf repo`_ uses pre-commit for validation of it's own content, and `ksconf-pre-commit repo`_ provides a pre-commit hook service definition for other repos.
    The first scenario is discussed in this section of the guide.
    The second scenario is for repositories that house Splunk apps to use :ref:`ksconf_cmd_check` and :ref:`ksconf_cmd_sort`
    as easy to use hooks against their own ``.conf`` files which is discussed further in :ref:`ksconf_pre_commit`.


Installing the pre-commit hook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To ensure your changes comply with the ksconf coding standards, please install and activate pre-commit_.

Install:

..  code-block:: sh

    pip install pre-commit

    # Register the pre-commit hooks (one time setup)
    cd ksconf
    pre-commit install --install-hooks

Install gitlint
~~~~~~~~~~~~~~~

Gitlint_ will check to ensure that commit messages are in compliance with the standard subject,
empty-line, and body format. You can enable it with:

..  code-block:: sh

    gitlint install-hook



Refresh module listing
----------------------

After making changes to the module hierarchy or simply adding new commands, refresh the listing for
the autodoc extension by running the following command. Note that this may not remove old packages.

..  code-block:: sh

    sphinx-apidoc --force -o "docs/source/api" ksconf 'ksconf/ext'



Create a new subcommand
-----------------------

Checklist:


#.  Create a new module in ``ksconf.commands.<CMD>``.

    -   Create a new class derived from :class:`KsconfCmd`.
        You must, at a minimum, define the following methods:

        -   ``register_args()`` to setup any config parser inputs.
        -   ``run()`` which handles the actual execution of the command.
#.  Register a new entrypoint configuration in the ``setup_entrypoints.py`` script.
    Edit the ``_entry_points`` dictionary to add an entry for the new command.

        - Each entry must include command name, module, and implementation class.
#.  Create unit tests in ``test/test_cli_<CMD>.py``.
#.  Create documentation in ``docs/source/cmd_<CMD>.rst.``
    You'll want to build the docs locally to make sure everything looks correct.
    Part of the documentation is automatically generated from the argparse arguments defined in the ``register_args()`` method,
    but other bits need to be spelled out explicitly.

When in doubt, it may be helpful to look back over history in git for other recently added commands and use that as an example.


Here's an overview of paths you should expect to update:

================================    ==========================================================================
File path                           Description / purpose
--------------------------------    --------------------------------------------------------------------------
================================    ==========================================================================
``ksconf/commands/fancy.py``        The core python code and CLI interface
``tests/tests/test_cli_CMD.py``     Add new unit test here
``docs/source/cmd_CMD.rst``         Command line documentation.  Make sure to include the `argparse` module
``ksconf/setup_entrypoints.py``     Addd a new entrypoint line here, or the new command won't be registered
``.pre-commit-hooks.yaml``          If a new command is applicable, add this to the `ksconf pre-commit repo`_.
``setup.py``                        Update if there are any new external dependencies
``requirements.txt``                Same as above
``make_splunk_app``                 If there's new dependencies that need to go into the Splunk app
================================    ==========================================================================


Cookiecutter options
--------------------

The following example assume we're make a new command called ``asciiart``:

..  code-block:: sh

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf

    # Kick off a cookiecutter  (promt submodule: asciiart)
    cookiecutter https://github.com/Kintyre/ksconf.git -c cookiecutter-subcommand

    cp ksconf-asciiart/* .

    git add ksconf/commands/*.py docs/source/cmd_*.rst tests/test_cli*.py

    # Merge that one line into entrypoints
    vim ksconf/setup_entrypoints*.py
    git add kconf/setup_entrypoints.py

    # Now run pre-commit to ensure that the new command is found successfully and is importable

    pre-commit
    # Now go write code, tests, docs and commit ...



..  include:: common
