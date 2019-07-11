Developer setup
===============

The following steps highlight the developer install process.

Tools
-----

If you are a developer, then we strongly suggest installing into a virtual environment to prevent
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
the following (for building docs, etc.):

..  code-block:: sh

    brew install homebrew/cask/mactex-no-gui


..  include:: common
