Developer setup
===============

The following steps highlight the developer install process.

Tools
-----

If you are a developer, then we strongly suggest installing into a virtual environment to prevent
overwriting the production version of ksconf and for the installation of the developer tools. (The
virtual environment name ``venv`` is used below, but this can be whatever suites, just make sure
not to commit it.)

..  code-block:: sh

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf

    # Setup and activate virtual environment
    python3 -m venv venv
    . venv/bin/activate

    # Install developer packages
    pip install -r requirements-dev.txt

    # Install the ksconf package in '--editable' mode
    pip install -e .

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
    . venv/bin/activate

    cd docs
    make html
    open build/html/index.html


If you are actively editing the docs, and would like changes to be updated in your browser as you save changes ``.rst`` files, then use the script in the root directory:

..  code-block:: sh

    ./make_docs


If you'd like to build PDF, then you'll need some extra tools. On Mac, you may also want to install
the following (for building docs, etc.):

..  code-block:: sh

    brew install homebrew/cask/mactex-no-gui



Running TOX
-----------

Local testing across multiple versions of python can be accomplished with tox_ and pyenv_.
See the online docs for theses tools for more details.

Tox and pyenv can be run like so:

..  code-block:: sh

    # Install the necessary python versions
    pyenv install 3.7.9
    ...
    pyenv install 3.10.1

    # Set specific default version of python for each major/minor release (tab completion is your friend here)
    pyenv local 3.7.9 ... 3.10.1

    # Run tox for ALL python versions
    tox

    # Run tox for just a specific python version
    tox -e py38

Some additional information about how to setup and run these tests can be gleaned from the ``Vagrantfile`` and ``Dockerfile``
in the root of the git repository, though specific python versions contained there may be quite out of date.

..  include:: common
