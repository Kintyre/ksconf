Kintyre's Splunk CONFiguration tool
===================================


Intro
-----

This utility handles a number of common Splunk app maintenance tasks in an installable python
package.  Specifically, this tools deals with many of the nuances with storing Splunk apps in a
version control system like git and pointing live Splunk apps to a working tree, merging changes
from the live system's (local) folder to the version controlled (default) folder, and dealing with
more than one layer of "default" (which splunk can't handle natively).


Install
-------

    pip install KintyreSplunkConfTool



Docs
----

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   license
   cli
   help



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
