..  _ksconf_cmd_filter:

ksconf filter
=============

..  argparse::
    :module: ksconf.__main__
    :func: build_cli_parser
    :path: filter
    :nodefault:


How is this different that btool?
---------------------------------

Some of the things filter can do does in fact overlap with :command:`btool list`.  Take for example:

..  code-block:: sh

    ksconf filter search/default/savedsearches.conf --stanza" Messages by minute last 3 hours"

Is essentially the same as:

..  code-block:: sh

    splunk btool --app=search savedsearches list "Messages by minute last 3 hours"

The output is the same, assuming that you didn't overwrite any part of that search in ``local``.
But if you take of the `--app` argument, you'll quickly see that ``btool`` is merging all the layers
together to show the final value of all attributes.  That is certainly a helpful thing to do,
but not always what you want.

Ksconf is always *only* looking at the file you explicitly pointed it to.  It's doesn't traverse the
tree on it's own.  This means that it works on app directory structure that live inside or outside
of your Splunk instance.  If you've ever tried to run ``btool check`` on an app that you haven't
installed yet, then you'll understand that value of this.

In many other cases, the usages of both ``ksconf filter`` and ``btool`` differ significantly.
But there is some overlap.



Can I do the same thing with standard unix tools?
-------------------------------------------------

Sure, go for it!

Yes, there's significant overlap with the filter command and what you can do with :command:`grep`,
:command:`awk`, or :command:`sed`.  Much of that is on purpose, and in fact some command line
arguments were borrowed.

I used to do this stuff my hand, but it's easy to screw up.  The idea of :command:`ksconf` is to
give you stable and reliable tools that are more suitable for ``.conf`` file work.  Also keep in
mind that these features are expanding, much more quickly that the unix tools change.

Although, if you've had to deal with BSD vs GNU tools and trying to find a set of common arguments,
then you probably already appreciate how awesome a domain-specific-tool like this is.
