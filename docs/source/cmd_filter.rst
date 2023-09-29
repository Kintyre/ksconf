..  _ksconf_cmd_filter:

ksconf filter
=============

..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: filter
    :nodefault:


How is this different that btool?
---------------------------------

Some of the things filter can do functionally overlaps with :command:`btool list`.  Take for example:

..  code-block:: sh

    ksconf filter search/default/savedsearches.conf --stanza "Messages by minute last 3 hours"

Is essentially the same as:

..  code-block:: sh

    splunk btool --app=search savedsearches list "Messages by minute last 3 hours"

The output is the same, assuming that you didn't overwrite any part of that search in ``local``.
But if you take off the ``--app`` argument, you'll quickly see that ``btool`` is merging all the layers
together to show the final value of all attributes.  That is certainly a helpful thing to do,
but not always what you want.

Ksconf is *only* going to look at the file you explicitly pointed it to.  It doesn't traverse the
tree on it's own.  This means that it works on app directory structure that live inside or outside
of your Splunk instance.  If you've ever tried to run ``btool check`` on an app that you haven't
installed yet, then you'll understand the value of this.

In many other cases, the usage of both ``ksconf filter`` and ``btool`` differ significantly.


..  note::  What if I want a filter default & local at the same time?

    In situations where it would be beneficial to filter based on the combined view of default and local, then simply use `ksconf_cmd_merge` first.
    Here are two options.


    *Option 1:*  Use a named temporary file

    ..  code-block:: sh

        ksconf merge search/{default,local}/savedsearches.conf > savedsearches.conf
        ksconf filter savedsearches.conf - --stanza "* last 3 hours"

    *Option 2:*  Chain both commands together


    ..  code-block:: sh

        ksconf merge search/{default,local}/savedsearches.conf | ksconf filter --stanza "* last 3 hours"



Examples
--------


Searching for attribute/values combinations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Find all enabled input stanzas with a sourcetype prefixed with ``apache:``.

..  code-block:: sh

    ksconf filter etc/apps/*/{default,local}/inputs.conf \
        --enabled-only --attr-eq sourcetype 'apache:*'


List the names of saved searches using potentially expensive search commands:

..  code-block:: sh

    ksconf filter etc/apps/*/{default,local}/savedsearches.conf \
        -b --match regex \
        --attr-eq search '.*\|\s*(streamstats|transaction) .*'


Show sourcetype stanzas where ``EVENT_BREAKER`` is defined but not enabled:

..  code-block:: sh

    ksconf filter etc/deployment-apps/*/{default,local}/props.conf \
        --skip-broken --match regex \
        --attr-match-equals EVENT_BREAKER '.+' \
        --attr-match-not-equals EVENT_BREAKER_ENABLE '(true|1)'

Note that both conditions listed must match for a stanza to match.  Logical 'AND' not an 'OR'.  Also note the use of ``--skip-broken`` because sometimes Splunk base apps have invalid conf files.


Lift and shift
~~~~~~~~~~~~~~

Copy all indexes defined within a specific app.

..  code-block:: sh

    cd $SPLUNK_DB
    for idx in $(ksconf filter $SPLUNK_HOME/etc/app/MyApp/default/indexes.conf --brief)
    do
        echo "Copy index ${idx}"
        tar -czf "/migrate/export-${idx}" "${idx}"
    done

Now you'll have a copy all of the necessary indexes in the :file:`/migrate` folder to make *MyApp* work on another Splunk instance.
Of course, there's likely other migration tasks to consider, like copying the actual app. This is just one way ksconf can help.



Can I do the same thing with standard unix tools?
-------------------------------------------------

Sure, go for it!

Yes, there's significant overlap with the filter command and what you can do with :command:`grep`,
:command:`awk`, or :command:`sed`.  Much of that is on purpose, and in fact some command line
arguments were borrowed.

I used to do these tasks by hand, but it's easy to make mistakes. The idea of :command:`ksconf` is to
give you stable and reliable tools that are more suitable for ``.conf`` file work.  Also keep in
mind that these features are expanding much more quickly than the unix tools change.

Although, if you've had to deal with BSD vs GNU tools and trying to find a set of common arguments,
then you probably already appreciate how awesome a domain-specific-tool like this is.
