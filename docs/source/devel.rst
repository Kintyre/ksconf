Developer setup
===============

The following steps highlight the developer install process.

Setup tools
-----------

If you are a developer then we strongly suggest installing into a virtual environment to prevent
overwriting the production version of ksconf and for the installation of the developer tools. (The
virtualenv name ``ksconfdev-pyve`` is used below, but this can be whatever suites, just make sure
not to commit it.)

..  code-block:: sh

    # Setup and activate virtual environment
    virtualenv ksconfdev-pyve
    . ksconfdev-pyve/bin/activate

    # Install developer packages
    pip install -r requirements-dev.txt

Install ksconf
--------------

..  code-block:: sh

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

Building the docs
-----------------

..  code-block:: sh

    cd ksconf
    . ksconfdev-pyve/bin/activate

    cd docs
    make html
    open build/html/index.html

If you’d like to build PDF, then you’ll need some extra tools. On Mac, you may also want to install
the following (for building docs, and the like):

..  code-block:: sh

    brew install homebrew/cask/mactex-no-gui

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

Note that this repo both uses pre-commit for it’s own validation (as discussed here) and provides a
pre-commit hook service to other repos.  This way repositories housing Splunk apps can, for example,
use ``ksconf --check`` or ``ksconf --sort`` against their own ``.conf`` files for validation
purposes.

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
---------------

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


..  include:: common
