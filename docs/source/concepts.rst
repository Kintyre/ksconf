Concepts
========


.. _configuration-layers:

Configuration layers
--------------------

The idea of configuration layers are used is shared across multiple actions in ksconf.
Specifically, :ref:`combine <ksconf_cmd_combine>` is used to merge multiple layers, and the
:ref:`unarchive <ksconf_cmd_unarchive>` command can be used to install or upgrade an app in a
layer-aware way.

What's the problem?
~~~~~~~~~~~~~~~~~~~

In a typical enterprise deployment of Splunk, a single app can easily have multiple logical sources
of configuration:

  (1) Upstream app developer (typically via Splunkbase)
  (2) Local developer app-developer adds organization-specific customizations or
      fixes
  (3) Splunk admin tweaks the inappropriate ``indexes.conf`` settings, and
  (4) Custom knowledge objects added by your subject matter experts.

Ideally we'd like to version control these, but doing so is complicated because normally you have to
manage all 4 of these logical layers in one 'default' folder.

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


.. _minimizing_files:

Minimizing files
----------------

What's the importance of minimizing files?

A typical scenario & why does this matter:

To customizing a Splunk app or add-on, many admins simply start by copying the conf file from
default to local and then applying your changes to the local file.  That's fine, but if you stopping
here you mave have just complicated future upgrades.  This is because the local file doesn't contain
*just* your settings, it contains all the default settings too.  So in the futre, fixes published by
the app creator may be masked by your local settings.  A better approach is to reduce the local conf
file leaving only the stanzas and settings that you indented to change.  This make your conf files
easier to read and makes upgrades easier, but it's tedious to do by hand.  Therefore, take a look at
the exact problem that the :ref:`minimize <ksconf_cmd_minimize>` command addresses.

.. important:: *Why all the fuss?*
   From the splunk docs

      "When you first create this new version of the file, **start with an empty file and add only
      the attributes that you need to change.** Do not start from a copy of the default directory. If you
      copy the entire default file to a location with higher precedence, any changes to the default
      values that occur through future Splunk Enterprise upgrades cannot take effect, because the
      values in the copied file will override the updated values in the default file."
      -- [SPLKDOC1]_.


.. [SPLKDOC1] https://docs.splunk.com/Documentation/Splunk/7.2.3/Admin/Configurationfiledirectories

.. include:: common
