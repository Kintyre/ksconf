Commands
========


.. We COULD import the breif description from each sub page, but that gets tedious.  Also, the breif listing provided here may end up being TOO breif for the subcommand page.
.. =================    ============================================
.. Command              Description
.. =================    ============================================
.. :doc:`cmd_sort`      Sort things
.. :doc:`cmd_diff`      .. include:: cmd_diff.rst
..                        :start-after: .. topic:: Summary
..                         :end-before: .. argparse
.. :doc:`cmd_diff`      .. include:: cmd_diff.rst
..                        :start-line: 2
..                        :end-line: 3
.. =================    ============================================



=====================  =========================================================
Command                Description
=====================  =========================================================
:doc:`cmd_check`       Perform basic syntax and sanity checks on .conf files
:doc:`cmd_combine`     Combine configuration files across multiple source
                       directories into a single destination directory. This
                       allows for an arbitrary number of splunk configuration
                       layers to coexist within a single app. Useful in both
                       ongoing merge and one-time ad-hoc use. For example,
                       combine can consolidate 'users' directory across
                       several instances after a phased server migration.
:doc:`cmd_diff`        Compare settings differences between two .conf files
                       ignoring spacing and sort order
:doc:`cmd_filter`      A stanza-aware GREP tool for conf files
:doc:`cmd_merge`       Merge two or more .conf files
:doc:`cmd_minimize`    Minimize the target file by removing entries
                       duplicated in the default conf(s)
:doc:`cmd_promote`     Promote .conf settings from one file into another
                       either in batch mode (all changes) or interactively
                       allowing the user to pick which stanzas and keys to
                       integrate. Changes made via the UI (stored in the
                       local folder) can be promoted (moved) to a version-
                       controlled directory.
:doc:`cmd_restexport`  Export .conf settings as a curl script to apply to a
                       Splunk instance later (via REST)
:doc:`cmd_snapshot`    Snapshot .conf file directories into a JSON dump
                       format
:doc:`cmd_sort`        Sort a Splunk .conf file creating a normalized format
                       appropriate for version control
:doc:`cmd_unarchive`   Install or upgrade an existing app in a git-friendly
                       and safe way
=====================  =========================================================




.. toctree::
   :maxdepth: 1
   :titlesonly:
   :glob:

   cmd_main

   cmd_*
