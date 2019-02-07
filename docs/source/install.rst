Installation Guide
==================

The following doc describes installation options for Kintyre's Splunk Configuration tool.  KSCONF is
available as a normal Python package that *should* require very minimal effort to install and
upgrade.  However, sometimes Python packaging gets ugly.

Because of the amount of the degree of complexity installing custom Python packages requires on many
enterprise-class Linux distributions which tend to ship with old versions and run for many years, we
decided to start shipping ``ksconf`` as a Splunk app.  While this isn't a traditional use-case for a
Splunk app, (because ``ksconf`` typically runs outside of Splunk, not from within it), it is a very
useful deployment mechanism.

For that reason, we suggest that most new users start with the `KSCONF app for Splunk`_ and only
fallback to the traditional Python-package based approach as needed.

If you do find that a python-level install is required or just preferable, then please take
advantage of the vast amount of install scenarios I documented *before* we build the KSCONF Splunk
app.  More notes and troubleshooting tips are located in the :doc:`install_advanced`.


Overview
--------

.. tabularcolumns:: |l|l|L|

+---------+-----------------------------------------------+------------------------------------------------+
|Install  | Advantages                                    | Potential pitfalls                             |
+=========+===============================================+================================================+
|Python   | - Most 'pure' and flexible way to install.    | - Lots of potential variations and pitfalls    |
|package  | - Many Linux distro's don't ship with ``pip`` | - Too many install options (complexity)        |
|         | - One command install.  (ideally)             | - Must consider/coordinate install user.       |
|         | - Easy upgrades                               | - Often requires some admin access.            |
+---------+-----------------------------------------------+------------------------------------------------+
|Splunk   | - Quick installation (single download)        | - No CLI completion (yet)                      |
|app      | - Requires one time bootstrap command         | - Can't add custom extensions (entrypoints)    |
|         | - Self contained; no admin access require     | - Crippled Python install (no ``pip``)         |
|         | - Great way to get started with minimal fuss. | - :ref:`Grandfather paradox`                   |
+---------+-----------------------------------------------+------------------------------------------------+
|Offline  | - Security: strict review and change control  | - Requires many steps.                         |
|package  | - See :doc:`install_advanced`.                | - Inherits 'Python package' pitfalls.          |
+---------+-----------------------------------------------+------------------------------------------------+



Quick install
-------------

Download and install the `KSCONF App for Splunk`_. Then open a shell, switch to the Splunk user
account and run this one-time bootstrap command.

.. code-block:: sh

   splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/bootstrap_bin.py

**Using pip**:

.. code-block:: sh

   pip install kintyre-splunk-conf

**System-level install**: (For Mac/Linux)

.. code-block:: sh

   curl https://bootstrap.pypa.io/get-pip.py | sudo python - kintyre-splunk-conf

.. note: PIP
   This will also install/update ``pip`` and work around some known TLS/SSL issues

**Enable Bash completion:**

If you're on a Mac or Linux, and would like to enable bash completion, run these commands:

.. code-block:: sh

   pip install argcomplete
   echo 'eval "$(register-python-argcomplete ksconf)"' >> ~/.bashrc

(Currently for Splunk APP installs; not because it can't work, but because it's not documented or
tested yet. Pull request welcome.)

Requirements
------------

*Python package install:*

 - `Python`_ Supports Python 2.7, 3.4+
 - `PIP <https://pip.pypa.io/en/stable/installing/>`__ (strongly recommended)
 - Tested on Mac, Linux, and Windows

*Splunk app install:*

 - Splunk 6.0 or greater is installed

Check Python version
~~~~~~~~~~~~~~~~~~~~

Check your installed python version by running:

.. code-block:: sh

   python --version

Note that Linux distributions and Mac OS X that ship with multiple version of Python may have
renamed this to ``python2``, ``python2.7`` or similar.

Check PIP Version
~~~~~~~~~~~~~~~~~

.. code-block:: sh

   pip --version

If you are running a different python interpreter version, you can instead run this as:

.. code-block:: sh

   python2.7 -m pip --version

Install from GIT
----------------

If you'd like to contribute to ksconf, or just build the latest and greatest, then install from the
git repository is a good choice.  (Technically this is still installing with ``pip``, so it's easy to
switch between a PyPI install, and a local install.)

.. code-block:: sh

   git clone https://github.com/Kintyre/ksconf.git
   cd ksconf
   pip install .

See `developer docs <devel.html>`__ for additional details about
contributing to ksconf.

Command line completion
-----------------------

Bash completion allows for a more intuitive interactive workflow by providing quick access to
command line options and file completions.  Often this saves time since the user can avoid mistyping
file names or be reminded of which command line actions and arguments are available without
switching contexts.  For example, if the user types ``ksconf d`` and hits :kbd:`Tab` then the
``ksconf diff`` is completed. Or if the user types ``ksconf`` and hits :kbd:`Tab` twice, the full
list of command actions are listed.

This feature uses the `argcomplete`_ Python package and supports Bash, zsh, tcsh.

Install via pip:

.. code-block:: sh

   pip install argcomplete

Enable command line completion for ksconf can be done in two ways.  The easiest option is to enable
it for ksconf only.  (However, it only works for the current user, it can break if the ksconf
command is referenced in a non-standard way.)  The alternate option is to enable global command line
completion for all python scripts at once, which is preferable if you use this module with many
python tool.

Enable argcomplete for ksconf only:

.. code-block:: sh

   # Edit your bashrc script
   vim ~.bashrc

   # Add the following line
   eval "$(register-python-argcomplete ksconf)"

   # Restart you shell, or just reload by running
   source ~/.bashrc

To enable argcomplete globally, run the command:

.. code-block:: sh

   activate-global-python-argcomplete

This adds new script to your the ``bash_completion.d`` folder, which can be use for all scripts and
all users, but it does add some minor overhead to each completion command request.

OS-specific notes:

-  **Mac OS X**: The global registration option has issue due the old version of Bash shipped by
   default. So either use the one-shot registration or install a later version of bash with
   homebrew:  ``brew install bash`` then. Switch to the newer bash by default with
   ``chsh /usr/local/bin/bash``.
-  **Windows**: Argcomplete doesn't work on windows Bash for GIT. See `argcomplete issue 142
   <https://github.com/kislyuk/argcomplete/issues/142>`__ for more info. If you really want this,
   use Linux subsystem for Windows instead.



.. _ksconf app for splunk: https://github.com/Kintyre/ksconf/releases/latest
.. _argcomplete: https://argcomplete.readthedocs.io/en/latest/
.. _python: https://www.python.org/downloads/
