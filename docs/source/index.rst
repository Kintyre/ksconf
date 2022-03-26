Kintyre's Splunk CONFiguration tool
===================================

..  image:: ../images/logo.png
    :alt: Ksconf logo

..  only:: builder_html or readthedocs

    ..  raw:: html

        <div style="display:inline-block; float:right; margin-top:25px">
        <a class="github-button" href="https://github.com/Kintyre/ksconf" data-icon="octicon-star" data-size="large" data-show-count="true" aria-label="Star Kintyre/ksconf on GitHub">Star</a>
        </div>
        <script async defer src="https://buttons.github.io/buttons.js"></script>

:Author: Lowell Alleman (Kintyre)
:Version: |version|

Welcome to KSCONF!
------------------

KSCONF is a modular command line tool for Splunk admins and app developers.
It's quick and easy to get started with basic commands and grow into the more advanced commands as needed.
Thank you for reviewing our expanding body of documentation to help smooth your transition to a more well-managed Splunk
environment and explore ways to integrate Ksconf capabilities into your existing workflow.

We are glad you are here! No matter where you're starting from, Ksconf can help. Let us
know if there is anything we can do to help along your journey.

    -- Kintyre team


Install
-------

Ksconf can be directly installed as a Python (via ``pip``) or as a Splunk app.  The Splunk app option is often easier.


To install as a **python package**, run the following:

..  code-block:: shell

    pip install ksconf


To install the **Splunk app**, download the latest `KSCONF App for Splunk`_ release.  Note that a
one-time registration command is needed to make ``ksconf`` executable:

..  code-block:: shell

    splunk cmd python3 $SPLUNK_HOME/etc/apps/ksconf/bin/install.py



User Guide
----------


..  toctree::
    :maxdepth: 2
    :caption: Contents

    intro
    concepts
    install
    cmd
    cheatsheet
    contrib
    devel
    git
    random
    contact_us

..  toctree::
    :maxdepth: 1
    :caption: Reference

    dyn/cli
    changelog
    known_issues
    install_advanced
    license
    api_ref



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. include:: common
