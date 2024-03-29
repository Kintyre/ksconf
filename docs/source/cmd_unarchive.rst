
..  _ksconf_cmd_unarchive:

ksconf unarchive
================

..  argparse::
    :module: ksconf.cli
    :func: build_cli_parser
    :path: unarchive
    :nodefault:

    --dest : @after
        Often this will be a git repository working tree where Splunk apps are stored.

    --app-name : @after
        Expanding archives that contain multiple (ITSI) or nested apps (NIX, ES) is not supported.

    --allow-local : @after
        Shipping local files is a Splunk app packaging violation so local files are blocked
        to prevent customizations from being overridden.

    --git-sanity-check : @replace
        By default, ``git status`` is run on the destination folder to detect working tree or
        index modifications before the unarchive process starts, but this is configurable.
        Sanity check choices go from least restrictive to most thorough:

        -   Use ``off`` to prevent any 'git status' safety checks.
        -   Use ``changed`` to abort only upon local modifications to files tracked by git.
        -   Use ``untracked`` (the default) to look for changed and untracked files before
            considering the tree clean.
        -   Use ``ignored`` to enable the most intense safety check which will abort if local
            changes, untracked, or ignored files are found.

    --git-mode : @after
        If a git commit is incorrect, simply roll it back with ``git reset`` or fix it with a
        ``git commit --amend`` before the changes are pushed anywhere else.  There's no native
        ``--dry-run`` or undo for unarchive mode because that's why you're using git in the first
        place, right? (Plus, such features would require significant overhead and unit testing.)

    SPL
        Supports tarballs (.tar.gz, .spl), and less-common zip files (.zip)


..  note:: What if I'm not using version control?

    Sanity checks and commit modes are automatically disabled if the app is being installed into a directory that is *not* contained within a git working tree.
    Ksconf confirms that `git` is present and functional before running sanity checks.


.. TODO:  Add some example stuff here...
