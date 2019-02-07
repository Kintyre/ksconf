Kintyre's Splunk CONFiguration tool
===================================

.. image:: ../images/logo.png
   :alt: Ksconf logo

Welcome to KSCONF |version|


Intro
-----

This utility handles a number of common Splunk app maintenance tasks surrounding the management of
``.conf`` files.
Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which Splunk can't handle natively).


Install
-------

Ksconf can be directly installed as a Python (via ``pip``) or as a Splunk app.
The python package approach has been the traditional option, but for many reasons isn't always easy
for non-python developers so we've added the Splunk app option to make things easier

.. note:: What's the difference?
   At this time the Splunk app approach should still be considered a "preview" feature.  But
   this is purely a question of distribution; the content and functionality is exactly the same no
   matter how you choose to install ksconf.

To install as a **python package**, run the following:

.. code-block:: shell

    pip install kintyre-splunk-conf

If you'd like to install via the Splunk app, download the latest
:file:`ksconf-app_for_splunk-{ver}.tgz` file from the GitHub releases page and install it into
Splunk.  Then, run the one-time registration command to make ``ksconf`` executable:

.. code-block:: shell

    splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/bootstrap_bin.py

This will add ``ksconf`` to Splunk's ``bin`` folder, thus making it executable either as ``ksconf``
or worse case ``splunk cmd ksconf``.  (If you can run ``splunk`` without giving it a path, then
``ksconf`` should work too.  At some point we may add an option for you to do this setup
step from the UI.



.. User Guide
.. ----


.. toctree::
   :maxdepth: 2
   :caption: Contents

   install
   cmd
   devel
   changelog
   known_issues
   license


.. toctree::
   :maxdepth: 1
   :caption: Reference

   cli
   install_advanced
   git


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
