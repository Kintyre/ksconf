Introduction
------------

:abbr:`ksconf (Kintyre's Splunk Configuration tool)`
is a command-line tool that helps administrators and developers manage their Splunk
environments by enhancing control of their configuration files.  By design, the interface is modular
so that each function (aka subcommand) can be learned quickly and used independently.  Most Ksconf
commands are simple enough to use for a quick one-off job, and yet designed to reliable enough to
integrate into complex app build and deployment workflows.

Ksconf helps manage the nuances with storing Splunk apps in a version control system, like git.  It
also supports pointing live Splunk apps to a working tree, merging changes from the live system's
(local) folder to the version controlled folder (often 'default'), and in more complex cases, it
deals with more than one :ref:`layer <configuration-layers>` of "default", which Splunk can't handle
natively).

.. note:: **What KSCONF is not**

   Ksconf does *not* replace your existing Splunk deployment mechanisms or version control tools.
   The goal is to complement and extend, not replace whatever workflow works for you.

Design principles
~~~~~~~~~~~~~~~~~

- **Ksconf is a toolbox.**  - Each tool has a specific purpose and function that works independently.  Borrowing from the Unix philosophy, each command should do one small thing well and be easily combined to handle higher-order tasks.
- **When possible, be familiar.** - Various commands borrow from popular UNIX command line tools such as “grep” and “diff”.  The overall modular nature of the command is similar to the modular interface used by “git” and the “splunk” cli.
- **Don’t impose workflow.** - Ksconf works with or without version control and independently of your deployment mechanisms.  (If you are looking to implement these things, ksconf is a great building block)
- **Embrace automated testing.** - It’s impractical to check every scenarios between each release, but significant work has gone into unittesting the CLI to avoid breaks between releases.

Common uses for ksconf
~~~~~~~~~~~~~~~~~~~~~~

- Promote changes from “local” to “default”
- Maintain multiple independent layers of configurations
- Reduce duplicate settings in a local file
- Upgrade apps stored in version control
- Merge or separate configuration files
- Git pre-commit hook for validation
- Git post-checkout hook for workflow automation
- Send .conf stanzas to a REST endpoint (Splunk Cloud or no file system access)
