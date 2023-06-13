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
        For one-time *combine* operations, the default banner can be suppressed by passing in an empty string (``''`` or ``""`` on Windows)


You may have noticed similarities between the ``combine`` and :ref:`merge <ksconf_cmd_merge>`
subcommands.  That's because under the covers they are using much of the same code.  The combine
operation essentially does a recursive merge between a set of directories.  One big difference is
that ``combine`` command will handle non-conf files intelligently, not just conf files.
Additionally, ``combined`` can automatically detect layers for you, depending on the layering scheme in use.


Mixing layers
-------------

Just like all layers can be managed independently, they can also be combined in any way you would like.
This also allows for different layers to be mixed-and-matched by selectively including layers to combine.
This feature is now available in ksconf 0.8.0 and later using the ``--include`` and ``--exclude`` CLI options,
which should behave as just as you'd expected.

..  note:: A more detailed explanation

    The ``--include`` and ``--exclude`` arguments are processed in the order given.
    These filters are applied to all layer names.
    The last match wins.

    If ``--include`` is first, then by default all layers, except for the ones explicitly included, will be excluded.
    Conversely, if ``--exclude`` is first, then all layers will be included except for the ones explicitly included.
    If *no* filters are given then all layers will be processed.

Here's an example, truncated for brevity, to further demonstrate how this can be used practically:

::

    Splunk_TA_nix/
    ├── README.txt
    ├── bin
    │   ├── bandwidth.sh
    │   ├── common.sh
    ├── default.d
    │   ├── 10-upstream
    │   │   ├── app.conf
    │   │   ├── data
    │   │   │   └── ui
    │   │   │       ├── nav
    │   │   │       │   └── default.xml
    │   │   │       └── views
    │   │   │           └── setup.xml
    │   │   ├── eventtypes.conf
    │   │   ├── inputs.conf
    │   │   ├── props.conf
    │   │   ├── tags.conf
    │   │   ├── transforms.conf
    │   │   └── web.conf
    │   ├── 20-common
    │   │   ├── inputs.conf
    │   │   ├── props.conf
    │   │   └── transforms.conf
    │   ├── 30-master-apps
    │   │   └── inputs.conf
    │   └── 30-shcluster-apps
    │       ├── inputs.conf
    │       └── web.conf
    ├── lookups
    │   ├── nix_da_update_status.csv
    │   ├── nix_da_version_ranges.csv
    └── metadata
        └── default.meta

Here we have several named layers in play:

 * ``10-upstream`` - the layer used to contain the default app content that ships from the Splunk TA, or whatever is "upstream" source is.
 * ``20-common`` - organizational level change to deployed everywhere.
 * ``30-master-apps`` - The bits that should just go to the indexers.
 * ``30-shcluster-apps`` - Content that should go to just the search heads.

In this case, we always want to combine the ``10-*`` and ``20-*`` layers, but only want to include either the master or searchhead cluster layer depending on server role.

..  code-block:: sh

    ksconf combine src/Splunk_TA_nix --target build/shcd/Splunk_TA_nix \
        --exclude=30-* --include=30-shcluster-apps
    ksconf combine src/Splunk_TA_nix --target build/cm/Splunk_TA_nix \
        --exclude=30-* --include=30-master-apps

    # Say you just want the original app, for some reason:
    ksconf combine src/Splunk_TA_nix --target /build/orig/Splunk_TA_nix --include=10-upstream


Using this technique you can pretty quickly write some simple shell scripts to build these all at once:

..  code-block:: sh

    for role in shcluster master
    do
        ksconf combine src/Splunk_TA_nix \
            --target build/${role}/Splunk_TA_nix \
            --exclude=30-* --include=30-${role}-apps
    done

Hopefully this gives you some ideas on how you can start to build some custom workflows with just a few small shell scripts.


Layer methods
-------------

Ksconf supports different methods of layer detection mechanism.
Right now just two different schemes are supported, but if you have other ways of organizing your layers, please :ref:`reach out <contact_us>`.

..

    Directory.d  (``dir.d``)
        Also known as ``*.d`` directory layout is allows layers to be embedded on a directory structure that allows for simple prioritization and labels to be applied to each layer.
        Anyone who's configured a Linux server should find this familiar.

            Example:  ``MyApp/default.d/10-my_layer/props.conf``

            Convention: ``<directory-name>.d/<##>-<layer-name>/``

        When these layers are combined, the top level folder is modified to remove the trailing ``.d``, and all content from the enable layers is combined within that folder.
        The layer-name portion of the path is discarded in the final combined path.
        Content is combined based on the assigned ranking of each layer, or directory sort order.

    Disable (legacy)
        If you would prefer to stick with the previous behavior (no automatic detection of layers) and specify all *SOURCE* directories manually, then use this mode.
        In this mode, each layer must be explicitly defined (or provide as a wildcard) and any other files operations must be handled elsewhere.

    Auto (default)
        In auto mode, if more than one source directory is given, then ``disable`` mode is used, if only a single directory is given then ``dir.d`` will be used.


How do I pick?
^^^^^^^^^^^^^^

.. tabularcolumns:: |c|L|L|

+-------------+----------------------------+--------------------------------+
|    Mode     | Useful when                | Avoid if                       |
+=============+============================+================================+
| ``dir.d``   | * Building a full app      | * Have existing ``.d`` folders |
|             | * If you need layers in    |   with other meaning           |
|             |   multiple places          | * Have multiple source         |
|             |   (``default.d``, and      |   directories.                 |
|             |   ``lookups.d``)           |                                |
|             | * If you sometimes have no |                                |
|             |   layers, then combine     |                                |
|             |   falls back to a file copy|                                |
+-------------+----------------------------+--------------------------------+
| ``disable`` | * Highly customized work   | * For app build scripts.       |
|             |   flows / full-control     |                                |
|             |   over combination logic   |                                |
+-------------+----------------------------+--------------------------------+


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
   │   ├── 10-upstream
   │   │   ├── app.conf
   │   │   ├── data
   │   │   │   └── ui
   │   │   │       ├── nav
   │   │   │       │   └── default.xml
   │   │   │       └── views
   │   │   │           ├── authentication_metrics.xml
   │   │   │           ├── cisco_security_overview.xml
   │   │   │           ├── getting_started.xml
   │   │   │           ├── search_ip_profile.xml
   │   │   │           ├── upgrading.xml
   │   │   │           └── user_tracking.xml
   │   │   ├── eventtypes.conf
   │   │   ├── macros.conf
   │   │   ├── savedsearches.conf
   │   │   └── transforms.conf
   │   ├── 20-my-org
   │   │   └── savedsearches.conf
   │   ├── 50-splunk-admin
   │   │   ├── indexes.conf
   │   │   ├── macros.conf
   │   │   └── transforms.conf
   │   └── 70-firewall-admins
   │       ├── data
   │       │   └── ui
   │       │       └── views
   │       │           ├── attacks_noc_bigscreen.xml
   │       │           ├── device_health.xml
   │       │           └── user_tracking.xml
   │       └── eventtypes.conf
   ├── lookups
   ├── metadata
   └── static



In this structure, you can see several layers of configurations at play:

    1.  The ``10-upstream`` layer appears to be the version of the default folder that shipped with
        the Cisco app.
    2.  The ``20-my-org`` layer is small and only contains tweaks to a few saved search entries.
    3.  The ``50-splunk-admin`` layer represents local settings changes to specify index
        configurations, and to augment the macros and transformations that ship with the default app.
    4.  And finally, ``70-firewall-admins`` contains some additional view (2 new, and 1 existing).
        Note that since ``user_tracking.xml`` is not a ``.conf`` file it will fully replace the
        upstream default version (that is, the file in ``10-upstream``)

You can merge all these layers inside this app into a new app folder using the command below:

..  code-block:: sh

    ksconf combine repo/Splunk_CiscoSecuritySuite --target=shcluster/apps/Splunk_CiscoSecuritySuite

``ksconf`` will automatically detect the ``default.d`` folder as a layer-containing directory and merge content from the detected layers (``10-upstream``, ``20-my-org``, ...) into a new ``default`` folder in the resulting app.
All other content (such as `README,` `bin`, `static`, `lookups` and so on) will be copied as-is.

.. versionchanged:: 0.8

    If you are using ``ksconf`` before 0.8, then you have to manually merge the layers, and possibly copy other top-level folders on your own (outside of ksconf).
    The example below still works fine after version 0.8, but the default behavior may change in 1.0, so it's advisable to start using ``--layer-method`` explicitly in any scripts you may use.

Here are the commands that could be used to generate a new (merged) ``default`` folder from all
of the layers shown above.

..  code-block:: sh

    cd Splunk_CiscoSecuritySuite
    ksconf combine default.d/* --target=default

Note that in the example above, the ``default`` folder now lives along side the ``default.d`` folder.
Also note that *only* the contents of ``default.d`` are copied, not the entire app, like in the above example.

..  seealso::

    The :ref:`unarchive <ksconf_cmd_unarchive>` command can be used to install or upgrade apps stored
    in a version controlled system in a layer-aware manor.


Consolidating 'users' directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``combine`` command can consolidate 'users' directory across several instances after a phased server migration.
See  :ref:`example_combine_user_folder`.
