ksconf combine
==============

What's the problem?
-------------------

Before diving into the ``combine`` command, let's look at the problem space.

In a typical enterprise deployment of Splunk, a single app can easily have multiple logical sources of configuration:

  (1) Upstream app developer (typically via Splunkbase)
  (2) Local developer app-developer adds organization-specific customizations or
      fixes
  (3) Splunk admin tweaks the inappropriate ``indexes.conf`` settings, and
  (4) Custom knowledge objects added by your subject matter experts.

Ideally we'd like to version control these, but doing so is complicated because normally you have to manage all 4 of these logical layers in one 'default' folder.

.. note:: Isn't that what the **local** folder is for?

   Splunk requires that app settings be located either in 'default' or 'local';
   and managing local files with version control leads to merge conflicts;
   so effectively, all version controlled settings need to be in 'default',
   or risk merge conflicts.

Let's suppose a new upstream version is released.  If you aren't managing layers independently, then
you have to manually upgrade the app being careful to preserve all custom configurations.  Compare
this to the solution provided by the 'combine' functionality.  Because logical sources can be
stored separately in their own directories changes can managed independently.  The changes in the
"upstream" layer will only ever be from official release; there's no combing through the commit log
to see what default was changed to figure out what custom changes need to be preserved and
reapplied.

While this doesn't completely remove the need for a human to review app upgrades, it does lower the
overhead enough that updates can be pulled in more frequently, thus reducing the divergence
potential.  (Merge frequently.)

.. note::  Mixing layers

   Just like all layers can be managed independently, they can also be combined in any way you'd
   like.  While this workflow is out side the scope of the examples provided here, it's a very
   doable use case.  This also allows for different layers to be mixed-and-matched by selectively
   including which layers to combine.


**ksconf combine**

.. _ksconf_cmd_combine:
.. argparse::
   :module: ksconf.__main__
   :func: build_cli_parser
   :path: combine
   :nodefault:


You may have noticed similarities between the ``combine`` and :ref:`merge <ksconf_cmd_merge>`
subcommands.  That's because under the covers they are using much of the same code.  The combine
operations essentially does a recursive merge between a set of directories.  One big difference is
that ``combine`` command will gracefully handle non-conf files intelligently, not just conf files.

Example
-------

Let's assume you have a directory structure that looks like this.   This example features the Cisco Security Suite.

::

   Splunk_CiscoSecuritySuite/
   ├── README
   ├── default.d
   │   ├── 10-upstream
   │   │   ├── app.conf
   │   │   ├── data
   │   │   │   └── ui
   │   │   │       ├── nav
   │   │   │       │   └── default.xml
   │   │   │       └── views
   │   │   │           ├── authentication_metrics.xml
   │   │   │           ├── cisco_security_overview.xml
   │   │   │           ├── getting_started.xml
   │   │   │           ├── search_ip_profile.xml
   │   │   │           ├── upgrading.xml
   │   │   │           └── user_tracking.xml
   │   │   ├── eventtypes.conf
   │   │   ├── macros.conf
   │   │   ├── savedsearches.conf
   │   │   └── transforms.conf
   │   ├── 20-my-org
   │   │   └── savedsearches.conf
   │   ├── 50-splunk-admin
   │   │   ├── indexes.conf
   │   │   ├── macros.conf
   │   │   └── transforms.conf
   │   └── 70-firewall-admins
   │       ├── data
   │       │   └── ui
   │       │       └── views
   │       │           ├── attacks_noc_bigscreen.xml
   │       │           ├── device_health.xml
   │       │           └── user_tracking.xml
   │       └── eventtypes.conf


In this structure, you can see several layers of configurations at play:

  1. The ``10-upstream`` layer appears to be the version of the default folder that shipped with
     the Cisco app.
  2. The ``20-my-org`` layer is small and only contains tweaks to a few savedsearch entires.
  3. The ``50-splunk-admin`` layer represents local settings changes to specify index
     configurations, and to augment the macros and transformations that ship with the default app.
  4. And finally, ``70-firewall-admins`` contains some additional view (2 new, and 1 existing).
     Note that since ``user_tracking.xml`` is not a ``.conf`` file it will fully replace the
     upstream default version (that is, the file in ``10-upstream``)

Here's are the commands that could be used to generate a new (merged) ``default`` folder from all
these layers shown above.

.. code-block:: sh

    cd Splunk_CiscoSecuritySuite
    ksconf combine default.d/* --target=default
