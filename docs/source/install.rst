Installation Guide
==================

KSCONF can be installed either as a Splunk app or a Python package.  Picking the option that's right
for you is fairly easy.

Unless you have experience with Python packaging or are planning on customizing or extending Ksconf, then the :ref:`Splunk app <install_splunk_app>` is likely the best place for you to start.
The native Python package works well for many developer-centric scenarios, but installation ends up being complicated for the more typical admin-centric use-case.
Therefore, most users will find it easier to start with the Splunk app.

.. note::

    The introduction of a Splunk app is a fairly new occurence (as of the 0.6.x release).
    Originally we resisted this idea, since ``ksconf`` was designed to manage other apps, not live within one.
    Ultimately however, the packaging decision was made to ensure users of all levels can utilize the program,
    as Python packaging is a mess and can be daunting for the uninitiated.


Overview
--------

.. tabularcolumns:: |l|L|L|

+---------+-----------------------------------------------+------------------------------------------------+
|Install  | Advantages                                    | Potential pitfalls                             |
+=========+===============================================+================================================+
|Python   | - Most 'pure' and flexible install            | - Lots of potential variations and pitfalls    |
|package  | - One command install.  (ideal)               | - Many Linux distro's don't ship with ``pip``  |
|         | - Easy upgrades                               | - Must consider/coordinate installation user.  |
|         | - More extendable (plugins)                   | - Often requires some admin access.            |
|         | - :ref:`install_python`                       | - Too many install options (complexity)        |
+---------+-----------------------------------------------+------------------------------------------------+
|Splunk   | - Quick installation (single download)        | - Crippled Python install (no ``pip``)         |
|app      | - Requires one time bootstrap command         | - Can't add custom extensions (entrypoints)    |
|         | - Self contained; no admin access require     | - No CLI completion (yet)                      |
|         | - Fast demo; fight with ``pip`` later         | - :ref:`Grandfather paradox`                   |
|         | - :ref:`install_splunk_app`                   |                                                |
+---------+-----------------------------------------------+------------------------------------------------+
|Offline  | - Security: strict review and change control  | - Requires many steps.                         |
|package  | - :doc:`install_advanced`.                    | - Inherits 'Python package' pitfalls.          |
+---------+-----------------------------------------------+------------------------------------------------+


Requirements
------------

*Python package install:*

 - `Python`_ Supports Python 2.7, 3.4+
 - `PIP <https://pip.pypa.io/en/stable/installing/>`__ (strongly recommended)
 - Tested on Mac, Linux, and Windows

*Splunk app install:*

 - Splunk 6.0 or greater is installed




.. _install_splunk_app:

Install Splunk App
------------------

Download and install the `KSCONF App for Splunk`_. Then open a shell, switch to the Splunk user
account and run this one-time bootstrap command.

.. code-block:: sh

   splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/install.py

On Windows, open a terminal as Administrator and type:

.. code-block:: batch

    cd "C:\Program Files\Splunk"
    bin\splunk.exe cmd python etc\apps\ksconf\bin\install.py


This will add ``ksconf`` to Splunk's ``bin`` folder, thus making it executable either as ``ksconf``
or, less optimally, ``splunk cmd ksconf``.  (If you can run ``splunk`` without giving it a path, then
``ksconf`` should work too.)

At some point we may add an option for you to do this setup step from the UI.

.. note:: Alternate download

   You can also download the latest (and pre-release) SPL from the `GitHub Releases`_ page.
   Download the file named like  :file:`ksconf-app_for_splunk-{ver}.tgz`


.. _install_python:

Install Python package
----------------------

Quick Install
~~~~~~~~~~~~~

**Using pip**:

.. code-block:: sh

   pip install kintyre-splunk-conf

**System-level install**: (For Mac/Linux)

.. code-block:: sh

   curl https://bootstrap.pypa.io/get-pip.py | sudo python - kintyre-splunk-conf

.. note: PIP
   This will also install/update ``pip`` and work around some known TLS/SSL issues


Enable Bash Completion
~~~~~~~~~~~~~~~~~~~~~~

Context-aware autocomplete can be a great time saver.
If you're on a Mac or Linux, and would like to enable bash completion, run these commands:

.. code-block:: sh

   pip install argcomplete
   echo 'eval "$(register-python-argcomplete ksconf)"' >> ~/.bashrc

(This option is not currently available for Splunk App installs due to a lack of documentation and testing available presently.
It should be possible.  Pull requests are welcome.)

Ran into issues?
~~~~~~~~~~~~~~~~

If you encounter any issues, please refer to the :doc:`install_advanced`.
Substantial time and effort was placed into the assembly of the information based on various scenarios we encountered.
A good place to begin would be in the :ref:`python_troubleshooting` section.


Install from GIT
----------------

If you'd like to contribute to ksconf, or just build the latest and greatest, then installing from the
git repository is a good choice.  (Technically this is still installing with ``pip``, so it's easy
to switch between a PyPI install, and a local install.)

.. code-block:: sh

   git clone https://github.com/Kintyre/ksconf.git
   cd ksconf
   pip install .

See :doc:`devel` for additional details about contributing to ksconf.



Validate the install
--------------------

No matter how you install ``ksconf``, you can confirm that it's working with the following command:

.. code-block:: sh

   ksconf --version

The output should look something like this:

::

                                      #
                                      ##
     ###  ##     #### ###### #######  ###  ##  #######
     ### ##     ###  ###           ## #### ##
     #####      ###  ###      ##   ## #######  #######
     ### ##     ###  ###      ##   ## ### ###  ##
     ###  ## #####    ######   #####  ###  ##  ##
                                            #

    ksconf 0.7.3  (Build 376)
    Python: 2.7.15  (/Applications/splunk/bin/python)
    Git SHA1 dc94f811 committed on 2019-06-05
    Installed at: /Applications/splunk/etc/apps/ksconf/bin/lib/ksconf
    Written by Lowell Alleman <lowell@kintyre.co>.
    Copyright (c) 2019 Kintyre Solutions, Inc, all rights reserved.
    Licensed under Apache Public License v2

      kintyre_splunk_conf  (0.7.3)

        Commands:
          check           (stable)    OK
          combine         (beta)      OK
          diff            (stable)    OK
          filter          (alpha)     OK
          merge           (stable)    OK
          minimize        (beta)      OK
          promote         (beta)      OK
          rest-export     (beta)      OK
          rest-publish    (alpha)     OK   (splunk-sdk 1.6.6)
          snapshot        (alpha)     OK
          sort            (stable)    OK
          unarchive       (beta)      OK
          xml-format      (alpha)     OK   (lxml 4.2.5)


Missing 3rd party libraries
~~~~~~~~~~~~~~~~~~~~~~~~~~~

..  note::  *Splunk app for KSCONF* users don't need to worry about this.

As of version 0.7.0, ksconf now includes commands that require external libraries.
But to keep the main package slim, these libraries aren't strictly required unless you want the specific commands.
As part of this change, :command:`ksconf --version` now reports any issues with individual commands in the 3rd column.
Any value other than 'OK' indicates a problem.
Here's an example of the output if you're missing the ``splunk-sdk`` package.

::

          ...
          promote         (beta)      OK
          rest-export     (beta)      OK
          rest-publish    (alpha)     Missing 3rd party module:  No module named splunklib.client
          snapshot        (alpha)     OK
          ...

Note that while the ``rest-publish`` command will not work in the example above, all of the other commands will continue to work fine.
If you don't need ``rest-publish`` then there's no need to do anything about it.
If you want the packages, install the "thirdparty" extras using the following command:

..  code-block:: sh

    pip install kintyre-splunk-conf[thirdparty]





Other issues
~~~~~~~~~~~~

If you run into any issues, check out the :ref:`adv_validate_install` section.



Command line completion
-----------------------

Bash completion allows for a more intuitive and interactive workflow by providing quick access to
command line options and file completions.  Often this saves time since the user can avoid mistyping
file names or be reminded of which command line actions and arguments are available without
switching contexts.  For example, if the user types ``ksconf d`` and hits :kbd:`Tab`, then the
``ksconf diff`` is completed. Or if the user types ``ksconf``, and hits :kbd:`Tab` twice, the full
list of command actions are listed.

This feature uses the `argcomplete`_ Python package and supports Bash, zsh, tcsh.

Install via pip:

.. code-block:: sh

   pip install argcomplete

Enabling command line completion for ksconf can be done in two ways.  The easiest option is to enable
it for ksconf only.  (However, it only works for the current user; it can break if the ksconf
command is referenced in a non-standard way.)  The alternate option is to enable global command line
completion for all python scripts at once, which is preferable if you use *argparse* for many python tools.

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

This adds a new script to your the ``bash_completion.d`` folder, which can be used for all scripts and
all users, but it does add some minor overhead to each completion command request.

OS-specific notes:

-  **Mac OS X**: The global registration option may not work as the old version of Bash was shipped by
   default. So either use the one-shot registration, or install a later version of bash with
   homebrew:  ``brew install bash`` then. Switch to the newer bash by default with
   ``chsh /usr/local/bin/bash``.
-  **Windows**: Argcomplete doesn't work on windows Bash for GIT. See `argcomplete issue 142
   <https://github.com/kislyuk/argcomplete/issues/142>`__ for more info. If you really want this,
   use Linux subsystem for Windows instead.




.. include:: common
