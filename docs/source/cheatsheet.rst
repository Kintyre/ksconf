Cheat Sheet
===========

.. I guess technically this is somewhere between a cheatsheet and tutorial???  but it works for now


Here's a quick rundown of handy ``ksconf`` commands:


..  note::

    Note that for clarity, most of the command line arguments are given in their long form,
    but many options also have a short form.

    Long commands may be broken across line for readability.   When this happens, a trailing
    backslash (``\``) is added so the command could still be copied verbatim into most shells.

    ..  only:: builder_epub

        Sorry ebook users.
        Trailing (``\``) probably will not look right on your screen.
        But then again, you probably won't be copy-n-pasting from your Kindle.

..  contents::


General purpose
---------------


Comparing files
~~~~~~~~~~~~~~~~

Show the differences between two conf files using :ref:`ksconf_cmd_diff`.

    .. code-block:: sh

        ksconf diff savedsearches.conf savedsearches-mine.conf


Sorting content
~~~~~~~~~~~~~~~

Create a normalized version of a configuration file, making conf files easier to merge with :command:`git`.
Run an in-place sort like so:

    .. code-block:: sh

        ksconf sort --inplace savedsearches.conf

..  tip::  Use the ``ksconf-sort`` :ref:`pre-commit<ksconf_pre_commit>` hook to do this for you.

Extract specific stanza
~~~~~~~~~~~~~~~~~~~~~~~


Say you want to *grep* your conf file for a specific stanza pattern:

    .. code-block:: sh

        ksconf filter search/default/savedsearches.conf --stanza 'Errors in the last *'


Say you want to list stanzas containing ``cron_schedule``:

    .. code-block:: sh

        ksconf filter Splunk_TA_aws/default/savedsearches.conf --brief \
            --attr-present 'cron_schedule'


Remove unwanted settings
~~~~~~~~~~~~~~~~~~~~~~~~

Say you want to remove ``vsid`` from a legacy savedsearches file:

    .. code-block:: sh

        ksconf filter search/default/savedsearches.conf --reject-attrs "vsid"


To see just to the schedule and scheduler status of scheduled searches, run:

    .. code-block:: sh

        ksconf filter Splunk_TA_aws/default/savedsearches.conf \
            --attr-present cron_schedule \
            --keep-attrs 'cron*' \
            --keep-attrs enableSched
            --keep-attrs disabled


Cleaning up
-----------


Reduce cruft in local
~~~~~~~~~~~~~~~~~~~~~~~

If you're in the habit of copying the *default* files to *local* in the TAs you deploy, here is a quick way to 'minimize' your files.
This will reduce the *local* file by removing all the *default* settings you copied but didn't change.
(The importance of this is outlined in :ref:`minimizing_files`.)

    .. code-block:: sh

        ksconf minimize Splunk_TA_nix/default/inputs.conf --target Splunk_TA_nix/local/inputs.conf


Pushing local changes to default
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

App developers can push changes from the :file:`local` folder to the :file:`default` folder:

    .. code-block:: sh

        ksconf promote --interactive myapp/local/props.conf myapp/default/props.conf

You will be prompted to pick which items you want to promote.
Alternatively, use the ``--batch`` option to promote everything in one step, without reviewing the changes first.


Packaging and building apps
---------------------------


Quick package and install
~~~~~~~~~~~~~~~~~~~~~~~~~


Use the ``--release-file`` option of the package command to write out the name of the final created tarball.
This helps when the final tarball name isn't known in advance because it contains a version string, for example.
By simply placing the latest release in a static location, this allows commonly repeated operations, like build+install be chained together in a convienent way making iterations quite fast from a shell.

    .. code-block:: sh

        cd my-apps
        ksconf package kintyre_app_speedtest --release-file .release && $SPLUNK_HOME/bin/splunk install app $(<.release) -update 1

To save time, I often put this command (along with a first-time install) command in a README or DEVELOPMENT file at the top-level of the app repo.

Advanced usage
---------------


Migrating content between apps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Say you want to move a bunch of savedsearches from ``search`` into a more appropriate app.
First create a file that lists all the names of your searches (one per line) in :file:`corp_searches.txt`.
Next, copy just the desired stanzas, those named in the 'corp_searches' file, over to your new :file:`corp_app` application.

    .. code-block:: sh

        ksconf filter --match string --stanza 'file://corp_searches.txt' \
            search/local/savedsearches.conf --output corp_app/default/savedsearches.conf

Now, to avoid duplication and confusion, you want to remove that exact same set of searches from the search app.

    .. code-block:: sh

        ksconf filter --match string --stanza 'file://corp_searches.txt' \
            --invert-match search/local/savedsearches.conf \
            --output search/local/savedsearches.conf.NEW

        # Backup the original
        mv search/local/savedsearches.conf \
            /my/backup/location/search-savedsearches-$(date +%Y%M%D).conf

        # Move the updated file in place
        mv search/local/savedsearches.conf.NEW search/local/savedsearches.conf


..  note::
    Setting the matching mode to ``string`` prevents any special characters that may be present in
    your search names from being interpreted as wildcards.


.. _example_combine_user_folder:

Migrating the 'users' folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Say you stood up a new Splunk server and the migration took longer than expected.
Now you have two :file:`users` folders and don't want to loose all the goodies stored in either one.
You've copied the users folder to :file:`user_old`.
You're working from the new server and would generally prefer to keep whatever is on the new server over what is on the old.
(This is because some of your users copied over some of their critical alerts manually while waiting for the migration to complete, and they've made updates they don't want to lose.)


After stopping Splunk on the new server, run the following commands.


    .. code-block:: sh

        mv /some/share/users_old  $SPLUNK_HOME/etc/users.old
        mv $SPLUNK_HOME/etc/users $SPLUNK_HOME/etc/users.new

        ksconf combine $SPLUNK_HOME/etc/users.old $SPLUNK_HOME/etc/users.new \
            --target $SPLUNK_HOME/etc/users --banner ''

Now double check the results and start Splunk.

We use the ``--banner`` option here to essential disable an output banner.
Because, in this case, the combine operation is a one-time job and therefore no warning is needed.


Maintaining apps stored in a local git repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    .. code-block:: sh

        ksconf unarchive


.. TODO - Finish this section





Putting it all together
-----------------------



Pulling out a stanza defined in both default and local
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Say you wanted to count the number of searches containing the word ``error``


    .. code-block:: sh

        ksconf merge default/savedsearches.conf local/savedsearches.conf \
            | ksconf filter - --stanza '*Error*' --ignore-case --count

This is a simple example of chaining two basic :program:`ksconf` commands together to perform a more complex operation.
The first command handles the merge of default and local :file:`savedsearches.conf` into a single output stream.
The second command filters the resulting stream finding stanzas containing the word 'Error'.



..  _example_ta_idx_tier:

Building an all-in one TA for your indexing tier
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Say you need to build a single TA containing all the index-time settings for your indexing tier.
(Note:  Enterprise Security does something similar when generating the indexer app.)

    .. code-block:: sh

        ksconf merge etc/apps/*TA*/{default,local}/props.conf \
            | ksconf filter --output=TA-for-indexers/default/props.conf \
              --include-attr 'TRANSFORMS*' \
              --include-attr 'TIME_*' \
              --include-attr 'MUST_BREAK*' \
              --include-attr 'SHOULD_LINEMERGE' \
              --include-attr 'EVENT_BREAKER*' \
              --include-attr 'LINE_BREAKER*'

This example is incomplete because it doesn't list *every* index-time :file:`props.conf` attribute, and leaves out :file:`transforms.conf` and :file:`fields.conf`, but hopefully you get the idea.



.. TODO - Add more examples of how you can combine multiple ksconf commands together in meaningful ways.  It's hard to find precise and relevant examples,
