Cheat Sheet
===========

.. I guess technically this is somewhere between a cheatsheet and tutorial???  but it works for now


Here's a quick rundown of handy ``ksconf`` commands:


..  note::

    Note that for clarity, most of the command line arguments are given in their long form.
    Many options also have a short form too.

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

Create a normalized version a configuration file, making conf files easier to merge with :command:`git`.
Run an in-place sort like so:

    .. code-block:: sh

        ksconf sort --inplace savedsearches.conf

..  tip::  Use the :ref:`ksconf-sort<pchook_ksconf-sort>` pre-commit hook to do this for you.

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

If you're in the habit of copying the *default* files to *local* in the TAs you deploy, here a quick way to 'minimize' your files.  This will reduce the *local* file by removing all the *default* settings you copied but didn't change.  (The importance of this is outlined in  :ref:`minimizing_files`.)

    .. code-block:: sh

        ksconf minimize Splunk_TA_nix/default/inputs.conf --target Splunk_TA_nix/local/inputs.conf


Pushing local changes to default
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

App developers can push changes from the :file:`local` folder over to the :file:`default` folder:

    .. code-block:: sh

        ksconf promote --interactive myapp/local/props.conf myapp/default/props.conf

You will be prompted to pick which items you want to promote.
Or use the ``--batch`` option to promote everything in one step, without reviewing the changes first.



Advanced usage
---------------


Migrating content between apps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Say you want to move a bunch of savedsearches from ``search`` into a more appropriate app.  First create a file that list all the names of your searches (one per line) in :file:`corp_searches.txt`

    .. code-block:: sh

        ksconf filter --match string --stanza 'file://corp_searches.txt' \
            search/local/savedsearches.conf --output corp_app/default/savedsearches.conf

And now, to avoid duplication and confusion, you want to remove that exact same set of searches from the search app.

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
You're working from the new server and would generally prefer to keep whatever on the new server over what's on the old.
(This is because some of your users copied over some of their critical alerts manually while waiting for the migration to complete, and they've made updates they don't want to lose.)


After stopping Splunk on the new server, run the following commands.


    .. code-block:: sh

        mv /some/share/users_old  $SPLUNK_HOME/etc/users.old
        mv $SPLUNK_HOME/etc/users $SPLUNK_HOME/etc/users.new

        ksconf combine $SPLUNK_HOME/etc/users.old $SPLUNK_HOME/etc/users.new \
            --target $SPLUNK_HOME/etc/users --banner ''

Now double check the results and start Splunk back up.

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

Say wanted to count the number of searches containing the word ``error``


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
(Note:  Enterprise Security does something similar this whenever they generate the indexer app.)

    .. code-block:: sh

        ksconf merge etc/apps/*TA*/{default,local}/props.conf \
            | ksconf filter --output=TA-for-indexers/default/props.conf \
              --include-attr 'TRANSFORMS*' \
              --include-attr 'TIME_*' \
              --include-attr 'MUST_BREAK*' \
              --include-attr 'SHOULD_LINEMERGE' \
              --include-attr 'EVENT_BREAKER*' \
              --include-attr 'LINE_BREAKER*'

This example is incomplete because it doesn't list *every* index-time :file:`props.conf` attribute, and leaves out file:`transforms.conf` and :file:`fields.conf`, but hopefully you get the idea.



.. TODO - Add more examples of how you can combine multiple ksconf commands together in meaningful ways.  It's hard to find precise and relevant examples,
