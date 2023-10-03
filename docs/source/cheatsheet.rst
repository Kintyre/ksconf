Cheat Sheet
===========

.. I guess technically this is somewhere between a cheatsheet and tutorial???  but it works for now


Here's a quick rundown of handy ``ksconf`` commands:


..  note::

    Note that for clarity, most of the command line arguments are given in their long form.

    Long commands may be broken across line for readability.   When this happens, a trailing
    backslash (``\``) is shown.  This can be copied verbatim into many shells.

    ..  only:: builder_epub

        Sorry ebook users.
        Trailing (``\``) probably will not look right on your screen.
        But then again, you probably won't be copy-n-pasting from your Kindle.

..  contents::


General purpose
---------------


Extracting a single value
~~~~~~~~~~~~~~~~~~~~~~~~~

Grabbing the definition of a single macro using :ref:`ksconf_cmd_attr-get`.
Note in the case of a complex or multi-line expression, any line continuation characters will be removed.

    .. code-block:: sh

        ksconf attr-get macros.conf --stanza 'unroll_json_array(6)' --attribute definition


Updating a single value
~~~~~~~~~~~~~~~~~~~~~~~

Suppose you have a macro called ``mydata_index`` that defines the source indexes for your dashboards.
The following command uses :ref:`ksconf_cmd_attr-set` to update that macro directly from the CLI without opening an editor.

    .. code-block:: sh

        ksconf attr-set macros.conf --stanza mydata_index --attribute definition --value 'index=mydata1 OR index=otheridx'

In this case the definition is a single line, but multi-line input is handled automatically.
It's also possible to pull a vale from an existing file or from an environment variable, should that be useful.


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


To see just to the scheduled time and enablement status of scheduled searches, run:

    .. code-block:: sh

        ksconf filter Splunk_TA_aws/default/savedsearches.conf \
            --attr-present cron_schedule \
            --keep-attrs 'cron*' \
            --keep-attrs enableSched
            --keep-attrs disabled

List apps configured in the deployment server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. code-block:: sh

        ksconf filter -b serverclass.conf --stanza 'serverClass:*:app:*' | \
            cut -d: -f4 | sort | uniq


Find saved searches with earliest=-1d@d
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. code-block:: sh

        ksconf filter apps/*/default/savedsearches.conf \
            --attr-eq dispatch.earliest_time "-1d@d"



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
By simply placing the latest release in a static location, this allows commonly repeated operations,
like build+install to be chained together in a convenient way making iterations quite fast.

    .. code-block:: sh

        cd my-apps
        ksconf package --release-file .release kintyre_app_speedtest &&
            "$SPLUNK_HOME/bin/splunk" install app "$(<.release)" -update 1

A build process for the same package, where the version is defined by the latest git tag, would look something like this:

    .. code-block:: sh

        ksconf package -f "dist/kintyre_app_speedtest-{{version}}.tar.gz" \
            --set-version="{{git_tag}}" \
            --set-build=$GITHUB_RUN_NUMBER \
            --release-file .release \
            kintyre_app_speedtest
        echo "Go upload $(<.release) to Splunkbase"



Advanced usage
---------------


Migrating content between apps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Say you want to move a bunch of savedsearches from ``search`` into a more appropriate app.
First create a file that lists all the names of your searches (one per line) in :file:`corp_searches.txt`.
Next, copy just the desired stanzas, to your new :file:`corp_app` application using the following command:

    .. code-block:: sh

        ksconf filter --match string --stanza 'file://corp_searches.txt' \
            search/local/savedsearches.conf --output corp_app/default/savedsearches.conf

Because we want to *move*, not just *copy*, the searches, they can now be removed from the search app using the following steps:

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

Using ``--banner`` essentially disables the output banner feature.
Because, in this case, the combine operation is a one-time job and therefore no top-of-file warning is needed.


Maintaining apps stored in a local git repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract and commit a new/updated app

    .. code-block:: sh

        ksconf unarchive --git-mode=commit my-package-112.tgz

For apps that use layers (``default.d`` folder), then use a command like so:

    .. code-block:: sh

        ksconf unarchive --git-mode=commit \
            --default-dir=default.d/10-upstream \
            --keep 'default.d/*' my-package-112.tgz

If you'd like to disable git hooks, like pre-commit, when importing a new release of
an upsteam app, add ``--git-commit-args="--no-verify`` to the above commands.



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
            | ksconf filter - --output=TA-for-indexers/default/props.conf \
              --include-attr 'TRANSFORMS*' \
              --include-attr 'TIME_*' \
              --include-attr 'MUST_BREAK*' \
              --include-attr 'SHOULD_LINEMERGE' \
              --include-attr 'EVENT_BREAKER*' \
              --include-attr 'LINE_BREAKER*'

This example is incomplete because it doesn't list *every* index-time :file:`props.conf` attribute, and leaves out :file:`transforms.conf` and :file:`fields.conf`, but hopefully you get the idea.



.. TODO - Add more examples of how you can combine multiple ksconf commands together in meaningful ways.  It's hard to find precise and relevant examples,
