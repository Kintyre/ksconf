ksconf unarchive
================

.. topic:: summary

   Unarchive (or install) some splunk apps.


.. _ksconf_cmd_unarchive:
.. argparse::
   :module: ksconf.__main__
   :func: build_cli_parser
   :path: unarchive
   :nodefault:

   --dest : @after
      Often this will be a git repository working tree where splunk apps are stored.

   --app-name : @after
      Expanding archives that contain multiple (ITSI) or nested apps (NIX, ES) is not supported.)

   --allow-local : @after
         Shipping local files is a Splunk app packaging violation so local files are blocked
         to prevent content from being overridden.

   --git-sanity-check : @replace
         By default ``git status`` is run on the destination folder to detect working tree or
         index modifications before the unarchive process starts, but this is configurable.
         Sanity check choices go from least restrictive to most thorough:

         - Use ``off`` to prevent any 'git status' safely checks.
         - Use ``changed`` to abort only upon local modifications to files tracked by git.
         - Use ``untracked`` (the default) to look for changed and untracked files before
           considering the tree clean.
         - Use ``ignored`` to enable the most intense safety check which will abort if local
           changes, untracked, or ignored files are found.

   --git-mode : @after
         If a git commit is incorrect, simply roll it back with ``git reset`` or fix it with a
         ``git commit --amend`` before the changes are pushed anywhere else.  There's no native
         ``--dry-run`` or undo for unarchive mode because that's why you're using git in the first
         place, right? (And such features would require significan't overhead and unittesting)

   SPL
         Supports tarballs (.tar.gz, .spl), and less-common zip files (.zip)


.. note:: Git features are automatically disabled

   Sanity checks and commit modes are automatically disabled if the app is being installed into a
   directory that is *not* a git working tree.  And this check is only done after first confirming that
   git is present and functional.
