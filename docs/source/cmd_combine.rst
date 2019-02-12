..  note:: Key concepts

    Before diving into the ``combine`` command, it may be helpful to brush up on the concept of
    :ref:`configuration layers <configuration-layers>`.


..  _ksconf_cmd_combine:

ksconf combine
==============

..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: combine
    :nodefault:

    --banner -b : @after
        For other on-going *combine* operations, it's helpful to inform any .conf file readers or potential editors that the file is automatically generated and therefore could be overwritten again.
        For one-time *combine* operations, the default banner can be suppresed by passing in an empty string (``''``)


You may have noticed similarities between the ``combine`` and :ref:`merge <ksconf_cmd_merge>`
subcommands.  That's because under the covers they are using much of the same code.  The combine
operations essentially does a recursive merge between a set of directories.  One big difference is
that ``combine`` command will gracefully handle non-conf files intelligently, not just conf files.


..  note::  Mixing layers

    Just like all layers can be managed independently, they can also be combined in any way you'd
    like.  While this workflow is out side the scope of the examples provided here, it's very doable.
    This also allows for different layers to be mixed-and-matched by selectively including which
    layers to combine.

Examples
--------

Merging a multilayer app
^^^^^^^^^^^^^^^^^^^^^^^^

Let's assume you have a directory structure that looks like the following.
This example features the Cisco Security Suite.

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

    1.  The ``10-upstream`` layer appears to be the version of the default folder that shipped with
        the Cisco app.
    2.  The ``20-my-org`` layer is small and only contains tweaks to a few savedsearch entires.
    3.  The ``50-splunk-admin`` layer represents local settings changes to specify index
        configurations, and to augment the macros and transformations that ship with the default app.
    4.  And finally, ``70-firewall-admins`` contains some additional view (2 new, and 1 existing).
        Note that since ``user_tracking.xml`` is not a ``.conf`` file it will fully replace the
        upstream default version (that is, the file in ``10-upstream``)

Here's are the commands that could be used to generate a new (merged) ``default`` folder from all
these layers shown above.

..  code-block:: sh

    cd Splunk_CiscoSecuritySuite
    ksconf combine default.d/* --target=default


..  seealso::

    The :ref:`unarchive <ksconf_cmd_unarchive>` command can be used to install or upgrade apps stored
    in a version controlled system in a layer-aware manor.


Consolidating 'users' directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``combine`` can consolidate 'users' directory across several instances after a phased server migration.
See  :ref:`example_combine_user_folder`.
