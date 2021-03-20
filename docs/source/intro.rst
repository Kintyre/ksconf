Introduction
------------

:abbr:`ksconf (Kintyre's Splunk Configuration tool)`
is a command-line tool that helps administrators and developers manage their Splunk environments by
enhancing their ability to control configuration files.  By design, the interface is modular so that
each function (aka subcommand) can be learned quickly and used independently.  Most Ksconf commands
are simple enough for a quick one-off job, yet reliable enough to integrate into complex app build
and deployment workflow.

Ksconf helps manage the nuances of storing Splunk apps in a version control system, such as git.  It
also supports pointing live Splunk apps to a working tree, merging changes from the live system's
(local) folder to the version controlled folder (often 'default'), and in more complex cases, it
deals with more than one :ref:`layer <configuration-layers>` of "default", which Splunk can't handle
natively.

.. note:: **What KSCONF is not**

    Ksconf does *not* replace your existing Splunk deployment mechanisms or version control tools.
    The goal is to complement and extend, not replace, the workflow that works for you.


Design principles
~~~~~~~~~~~~~~~~~

**Ksconf is a toolbox.**
    Each tool has a specific purpose and function that works independently.
    Borrowing from the Unix philosophy, each command should do one thing well and be easily combined
    to handle higher-order tasks.

**When possible, be familiar.**
    Various commands borrow from popular UNIX command line tools such as :command:`grep` and
    :command:`diff`.  The modular nature of the command and other design features were borrowed from
    :command:`git` and :command:`splunk` as well.

**Don’t impose workflow.**
    Ksconf works with or without version control and independently of your deployment mechanisms.
    If you are looking to implement these things, Ksconf is a great building block.

**Embrace automated testing.**
    It's impractical to check every scenario between each release, but significant work has gone
    into unit testing the CLI to avoid breakage.


Common uses for Ksconf
~~~~~~~~~~~~~~~~~~~~~~

- Build and package Splunk apps
- Promote changes from :file:`local` to :file:`default`
- Maintain multiple independent layers of configurations
- Reduce duplicate settings in a local file
- Upgrade apps stored in version control
- Merge or separate configuration files
- Git pre-commit hook for validation
- Git post-checkout hook for workflow automation
- Send *.conf* stanzas to a REST endpoint (Splunk Cloud or no file system access)


Getting started
~~~~~~~~~~~~~~~

You're in the right place. If you are a beginner, try checking these out first:

-   :doc:`cheatsheet` - Like jumping in the deep end, or prefer examples of descriptions?  Start here.
-   :doc:`concepts` - To get a more theoretical background on why these things matter.
-   :doc:`cmd` -  Start here if you'd like a more thorough introduction.
