Kintyre's Splunk CONFiguration tool
===================================

.. image:: ../images/logo.png
   :alt: Ksconf logo

Welcome to KSCONF |version|

Ksconf is a command-line tool that helps administrators and developers manage their Splunk
environments by enhancing control of their configuration files.  The interface is
modular, making it easy to learn and independent.  The implementation is robust with automated
unittests and coverage monitoring for any regressions.


Install
-------

Ksconf can be directly installed as a Python (via ``pip``) or as a Splunk app.  The Splunk app option is often easier.


To install as a **python package**, run the following:

.. code-block:: shell

    pip install kintyre-splunk-conf


To install the **Splunk app**, download the latest `KSCONF App for Splunk`_ release.  Note that a
one-time registration command is need to make ``ksconf`` executable:

.. code-block:: shell

    splunk cmd python $SPLUNK_HOME/etc/apps/ksconf/bin/bootstrap_bin.py



.. User Guide
.. ----


.. toctree::
   :maxdepth: 2
   :caption: Contents

   intro
   concepts
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
   random
   modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. include:: common
