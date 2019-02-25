Command line reference
######################


KSCONF supports the following CLI options:

.. _ksconf_cli:

ksconf
******

 .. code-block:: none

    usage: ksconf [-h] [--version] [--force-color]
                  {check,combine,diff,filter,promote,merge,minimize,snapshot,sort,rest-export,rest-publish,unarchive}
                  ...
    
    Ksconf: Kintyre Splunk CONFig tool
    
    This utility handles a number of common Splunk app maintenance tasks in a small
    and easy to deploy package.  Specifically, this tools deals with many of the
    nuances with storing Splunk apps in git, and pointing live Splunk apps to a git
    repository.  Merging changes from the live system's (local) folder to the
    version controlled (default) folder, and dealing with more than one layer of
    "default" (which splunk can't handle natively) are all supported tasks.
    
    positional arguments:
      {check,combine,diff,filter,promote,merge,minimize,snapshot,sort,rest-export,rest-publish,unarchive}
        check               Perform basic syntax and sanity checks on .conf files
        combine             Combine configuration files across multiple source
                            directories into a single destination directory. This
                            allows for an arbitrary number of splunk configuration
                            layers to coexist within a single app. Useful in both
                            ongoing merge and one-time ad-hoc use.
        diff                Compare settings differences between two .conf files
                            ignoring spacing and sort order
        filter              A stanza-aware GREP tool for conf files
        promote             Promote .conf settings between layers using either
                            either in batch mode (all changes) or interactive
                            mode. Frequently this is used to promote conf changed
                            made via the UI (stored in the 'local' folder) to a
                            version-controlled directory, often 'default'.
        merge               Merge two or more .conf files
        minimize            Minimize the target file by removing entries
                            duplicated in the default conf(s)
        snapshot            Snapshot .conf file directories into a JSON dump
                            format
        sort                Sort a Splunk .conf file creating a normalized format
                            appropriate for version control
        rest-export         Export .conf settings as a curl script to apply to a
                            Splunk instance later (via REST)
        rest-publish        Publish .conf settings to a live Splunk instance via
                            REST
        unarchive           Install or upgrade an existing app in a git-friendly
                            and safe way
    
    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      --force-color         Force TTY color mode on. Useful if piping the output a
                            color-aware pager, like 'less -R'



.. _ksconf_cli_check:

ksconf check
************

 .. code-block:: none

    usage: ksconf check [-h] [--quiet] FILE [FILE ...]
    
    Provide basic syntax and sanity checking for Splunk's .conf files. Use
    Splunk's builtin 'btool check' for a more robust validation of keys and
    values. Consider using this utility as part of a pre-commit hook.
    
    positional arguments:
      FILE         One or more configuration files to check. If '-' is given, then
                   read a list of files to validate from standard input
    
    optional arguments:
      -h, --help   show this help message and exit
      --quiet, -q  Reduce the volume of output.



.. _ksconf_cli_combine:

ksconf combine
**************

 .. code-block:: none

    usage: ksconf combine [-h] [--target TARGET] [--dry-run] [--banner BANNER]
                          source [source ...]
    
    Merge .conf settings from multiple source directories into a combined target
    directory.   Configuration files can be stored in a '/etc/*.d' like directory
    structure and consolidated back into a single 'default' directory.
    
    This command supports both one-time operations and recurring merge jobs.  For
    example, this command can be used to combine all users knowledge objects (stored
    in 'etc/users') after a server migration, or to merge a single user's settings
    after an their account has been renamed.  Recurring operations assume some type
    of external scheduler is being used.  A best-effort is made to only write to
    target files as needed.
    
    The 'combine' command takes your logical layers of configs (upstream, corporate,
    splunk admin fixes, and power user knowledge objects, ...) expressed as
    individual folders and merges them all back into the single 'default' folder
    that Splunk reads from.  One way to keep the 'default' folder up-to-date is
    using client-side git hooks.
    
    No directory layout is mandatory, but but one simple approach is to model your
    layers using a prioritized 'default.d' directory structure. (This idea is
    borrowed from the Unix System V concept where many services natively read their
    config files from '/etc/*.d' directories.)
    
    positional arguments:
      source                The source directory where configuration files will be
                            merged from. When multiple sources directories are
                            provided, start with the most general and end with the
                            specific; later sources will override values from the
                            earlier ones. Supports wildcards so a typical Unix
                            'conf.d/##-NAME' directory structure works well.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target TARGET, -t TARGET
                            Directory where the merged files will be stored.
                            Typically either 'default' or 'local'
      --dry-run, -D         Enable dry-run mode. Instead of writing to TARGET,
                            preview changes as a 'diff'. If TARGET doesn't exist,
                            then show the merged file.
      --banner BANNER, -b BANNER
                            A warning banner to discourage manual editing of conf
                            files.



.. _ksconf_cli_diff:

ksconf diff
***********

 .. code-block:: none

    usage: ksconf diff [-h] [-o FILE] [--comments] CONF1 CONF2
    
    Compares the content differences of two .conf files
    
    This command ignores textual differences (like order, spacing, and comments) and
    focuses strictly on comparing stanzas, keys, and values.  Note that spaces
    within any given value will be compared.  Multi-line fields are compared in are
    compared in a more traditional 'diff' output so that long savedsearches and
    macros can be compared more easily.
    
    positional arguments:
      CONF1                 Left side of the comparison
      CONF2                 Right side of the comparison
    
    optional arguments:
      -h, --help            show this help message and exit
      -o FILE, --output FILE
                            File where difference is stored. Defaults to standard
                            out.
      --comments, -C        Enable comparison of comments. (Unlikely to work
                            consistently)



.. _ksconf_cli_filter:

ksconf filter
*************

 .. code-block:: none

    usage: ksconf filter [-h] [-o FILE] [--comments] [--verbose]
                         [--match {regex,wildcard,string}] [--ignore-case]
                         [--invert-match] [--files-with-matches]
                         [--count | --brief] [--stanza PATTERN]
                         [--attr-present ATTR] [--keep-attrs WC-ATTR]
                         [--reject-attrs WC-ATTR]
                         CONF [CONF ...]
    
    Filter the contents of a conf file in various ways. Stanzas can be included or
    excluded based on provided filter, based on the presents or value of a key.
    Where possible, this command supports GREP-like arguments to bring a familiar
    feel.
    
    positional arguments:
      CONF                  Input conf file
    
    optional arguments:
      -h, --help            show this help message and exit
      -o FILE, --output FILE
                            File where the filtered results are written. Defaults
                            to standard out.
      --comments, -C        Preserve comments. Comments are discarded by default.
      --verbose             Enable additional output.
      --match {regex,wildcard,string}, -m {regex,wildcard,string}
                            Specify pattern matching mode. Defaults to 'wildcard'
                            allowing for '*' and '?' matching. Use 'regex' for
                            more power but watch out for shell escaping. Use
                            'string' enable literal matching.
      --ignore-case, -i     Ignore case when comparing or matching strings. By
                            default matches are case-sensitive.
      --invert-match, -v    Invert match results. This can be used to show what
                            content does NOT match, or make a backup copy of
                            excluded content.
    
    Output mode:
      Select an alternate output mode. If any of the following options are used,
      the stanza output is not shown.
    
      --files-with-matches, -l
                            List files that match the given search criteria
      --count, -c           Count matching stanzas
      --brief, -b           List name of matching stanzas
    
    Stanza selection:
      Include or exclude entire stanzas using these filter options. All filter
      options can be provided multiple times. If you have a long list of
      filters, they can be saved in a file and referenced using the special
      'file://' prefix.
    
      --stanza PATTERN      Match any stanza who's name matches the given pattern.
                            PATTERN supports bulk patterns via the 'file://'
                            prefix.
      --attr-present ATTR   Match any stanza that includes the ATTR attribute.
                            ATTR supports bulk attribute patterns via the
                            'file://' prefix.
    
    Attribute selection:
      Include or exclude attributes passed through. By default all attributes
      are preserved. Whitelist (keep) operations are preformed before blacklist
      (reject) operations.
    
      --keep-attrs WC-ATTR  Select which attribute(s) will be preserved. This
                            space separated list of attributes indicates what to
                            preserve. Supports wildcards.
      --reject-attrs WC-ATTR
                            Select which attribute(s) will be discarded. This
                            space separated list of attributes indicates what to
                            discard. Supports wildcards.



.. _ksconf_cli_promote:

ksconf promote
**************

 .. code-block:: none

    usage: ksconf promote [-h] [--batch | --interactive] [--force] [--keep]
                          [--keep-empty]
                          SOURCE TARGET
    
    Propagate .conf settings applied in one file to another.  Typically this is used
    to move 'local' changes (made via the UI) into another layer, such as the
    'default' or a named 'default.d/50-xxxxx') folder.
    
    Promote has two modes:  batch and interactive.  In batch mode all changes are
    applied automatically and the (now empty) source file is removed.  In interactive
    mode the user is prompted to select stanzas to promote.  This way local changes
    can be held without being promoted.
    
    NOTE: Changes are *MOVED* not copied, unless '--keep' is used.
    
    positional arguments:
      SOURCE             The source configuration file to pull changes from.
                         Typically the 'local' conf file)
      TARGET             Configuration file or directory to push the changes into.
                         (Typically the 'default' folder) As a shortcut, if a
                         directory is given, it's assumed that the same basename
                         is used for both SOURCE and TARGET.
    
    optional arguments:
      -h, --help         show this help message and exit
      --batch, -b        Use batch mode where all configuration settings are
                         automatically promoted. All changes are removed from
                         source and applied to target. The source file will be
                         removed, unless '--keep-empty' is used.
      --interactive, -i  Enable interactive mode where the user will be prompted
                         to approve the promotion of specific stanzas and
                         attributes. The user will be able to apply, skip, or edit
                         the changes being promoted.
      --force, -f        Disable safety checks. Don't check to see if SOURCE and
                         TARGET share the same basename.
      --keep, -k         Keep conf settings in the source file. All changes will
                         be copied into the target file instead of being moved
                         there. This is typically a bad idea since local always
                         overrides default.
      --keep-empty       Keep the source file, even if after the settings
                         promotions the file has no content. By default, SOURCE
                         will be removed after all content has been moved into
                         TARGET. Splunk will re-create any necessary local files
                         on the fly.



.. _ksconf_cli_merge:

ksconf merge
************

 .. code-block:: none

    usage: ksconf merge [-h] [--target FILE] [--dry-run] [--banner BANNER]
                        FILE [FILE ...]
    
    Merge two or more .conf files into a single combined .conf file.  This could be
    used to merge the props.conf file from ALL technology addons into a single file:
    
    ksconf merge --target=all-ta-props.conf etc/apps/*TA*/{default,local}/props.conf
    
    positional arguments:
      FILE                  The source configuration file to pull changes from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            Save the merged configuration files to this target
                            file. If not provided. the merged conf is written to
                            standard output.
      --dry-run, -D         Enable dry-run mode. Instead of writing to TARGET,
                            preview changes in 'diff' format. If TARGET doesn't
                            exist, then show the merged file.
      --banner BANNER, -b BANNER
                            A banner or warning comment added to the top of the
                            TARGET file. This is often used to warn Splunk admins
                            from editing an auto-generated file.



.. _ksconf_cli_minimize:

ksconf minimize
***************

 .. code-block:: none

    usage: ksconf minimize [-h] [--target TARGET] [--dry-run | --output OUTPUT]
                           [--explode-default] [-k PRESERVE_KEY]
                           CONF [CONF ...]
    
    Minimize a conf file by removing the default settings
    
    Reduce local conf file to only your indented changes without manually tracking
    which entries you've edited.  Minimizing local conf files makes your local
    customizations easier to read and often results in cleaner add-on upgrades.
    
    positional arguments:
      CONF                  The default configuration file(s) used to determine
                            what base settings are unnecessary to keep in the
                            target file.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target TARGET, -t TARGET
                            The local file that you wish to remove duplicate
                            settings from. By default, this file will be read from
                            and then updated with a minimized version.
      --dry-run, -D         Enable dry-run mode. Instead of writing the minimizing
                            the TARGET file, preview what would be removedthe form
                            of a 'diff'.
      --output OUTPUT       Write the minimized output to a separate file instead
                            of updating TARGET.
      --explode-default, -E
                            Enable minimization across stanzas as well as files
                            for special use-cases
      -k PRESERVE_KEY, --preserve-key PRESERVE_KEY
                            Specify attributes that should always be kept.



.. _ksconf_cli_snapshot:

ksconf snapshot
***************

 .. code-block:: none

    usage: ksconf snapshot [-h] [--output FILE] [--minimize] PATH [PATH ...]
    
    Build a static snapshot of various configuration files stored within a
    structured json export format. If the .conf files being captured are within a
    standard Splunk directory structure, then certain metadata is assumed based on
    path locations. Otherwise, less metadata is recorded. ksconf snapshot
    --output=daily.json /opt/splunk/etc/app/
    
    positional arguments:
      PATH                  Directory from which to load configuration files. All
                            .conf and .meta file are included recursively.
    
    optional arguments:
      -h, --help            show this help message and exit
      --output FILE, -o FILE
                            Save the snapshot to the named files. If not provided,
                            the snapshot is written to standard output.
      --minimize            Reduce the size of the JSON output by removing
                            whitespace. Reduces readability.



.. _ksconf_cli_sort:

ksconf sort
***********

 .. code-block:: none

    usage: ksconf sort [-h] [--target FILE | --inplace] [-F] [-q] [-n LINES]
                       FILE [FILE ...]
    
    Sort a Splunk .conf file.  Sort has two modes:  (1) by default, the sorted
    config file will be echoed to the screen.  (2) the config files are updated
    in-place when the -i' option is used.
    
    Manually managed conf files can be blacklisted by add a comment containing the
    string 'KSCONF-NO-SORT' to the top of any .conf file.
    
    positional arguments:
      FILE                  Input file to sort, or standard input.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            File to write results to. Defaults to standard output.
      --inplace, -i         Replace the input file with a sorted version. Warning
                            this a potentially destructive operation that may
                            move/remove comments.
      -n LINES, --newlines LINES
                            Lines between stanzas.
    
    In-place update arguments:
      -F, --force           Force file sorting for all files, even for files
                            containing the special 'KSCONF-NO-SORT' marker.
      -q, --quiet           Reduce the output. Reports only updated or invalid
                            files. This is useful for pre-commit hooks, for
                            example.



.. _ksconf_cli_rest-export:

ksconf rest-export
******************

 .. code-block:: none

    usage: ksconf rest-export [-h] [--output FILE] [--disable-auth-output]
                              [--pretty-print] [-u | -D] [--url URL] [--app APP]
                              [--user USER] [--owner OWNER] [--conf TYPE]
                              [--extra-args EXTRA_ARGS]
                              CONF [CONF ...]
    
    Build an executable script of the stanzas in a configuration file that can be later applied to
    a running Splunk instance via the Splunkd REST endpoint.
    
    This can be helpful when pushing complex props & transforms to an instance where you only have
    UI access and can't directly publish an app.
    
    positional arguments:
      CONF                  Configuration file(s) to export settings from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --output FILE, -t FILE
                            Save the shell script output to this file. If not
                            provided, the output is written to standard output.
      -u, --update          Assume that the REST entities already exist. By
                            default output assumes stanzas are being created.
                            (This is an unfortunate quark of the configs REST API)
      -D, --delete          Remove existing REST entities. This is a destructive
                            operation. In this mode, stanzas attributes are
                            unnecessary and ignored. NOTE: This works for 'local'
                            entities only; the default folder cannot be updated.
      --url URL             URL of Splunkd. Default: https://localhost:8089
      --app APP             Set the namespace (app name) for the endpoint
      --user USER           Deprecated. Use --owner instead.
      --owner OWNER         Set the object owner. Typically the default of
                            'nobody' is ideal if you want to share the
                            configurations at the app-level.
      --conf TYPE           Explicitly set the configuration file type. By default
                            this is derived from CONF, but sometime it's helpful
                            set this explicitly. Can be any valid Splunk conf file
                            type, example include 'app', 'props', 'tags',
                            'savedsearches', and so on.
      --extra-args EXTRA_ARGS
                            Extra arguments to pass to all CURL commands. Quote
                            arguments on the command line to prevent confusion
                            between arguments to ksconf vs curl.
    
    Output Control:
      --disable-auth-output
                            Turn off sample login curl commands from the output.
      --pretty-print, -p    Enable pretty-printing. Make shell output a bit more
                            readable by splitting entries across lines.



.. _ksconf_cli_rest-publish:

ksconf rest-publish
*******************

 .. code-block:: none

    usage: ksconf rest-publish [-h] [--conf TYPE] [-m META] [--url URL]
                               [--user USER] [--pass PASSWORD] [-k] [--app APP]
                               [--owner OWNER] [--sharing {user,app,global}] [-D]
                               CONF [CONF ...]
    
    Publish stanzas in a .conf file to a running Splunk instance via REST. This
    requires access to the HTTPS endpoint of splunk. By default, ksconf will
    handle both the creation of new stanzas and the update of exists stanzas
    without user interaction. This can be used to push full configuration stanzas
    where you only have REST access and can't directly publish an app. In dry-run
    mode, the output of what would be pushed is shown. Keep in mind that ONLY the
    attributes present in the conf file are pushed. Therefore it's possible for
    the source .conf file to ultimately differ from what ends up on the server's
    .conf file. To avoid this, you could remove the object using '--delete' mode
    and then insert a new copy of the object. This will make the object
    unavailable for a short period of time. Be aware that, for consistency, the
    configs/conf-TYPE endpoint is used for this command. Therefore, a reload may
    be required for the server to use the published config settings.
    
    positional arguments:
      CONF                  Configuration file(s) to export settings from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --conf TYPE           Explicitly set the configuration file type. By default
                            this is derived from CONF, but sometime it's helpful
                            set this explicitly. Can be any valid Splunk conf file
                            type, example include 'app', 'props', 'tags',
                            'savedsearches', and so on.
      -m META, --meta META  Specify one or more '.meta' files to determine the
                            desired read & write ACLs, owner, and sharing for
                            objects in the CONF file.
      --url URL             URL of Splunkd. Default: https://localhost:8089
      --user USER           Login username Splunkd. Default: admin
      --pass PASSWORD       Login password Splunkd. Default: changeme
      -k, --insecure        Disable SSL cert validation.
      --app APP             Set the namespace (app name) for the endpoint
      --owner OWNER         Set the user who owns the content. The default of
                            'nobody' works well for app-level sharing.
      --sharing {user,app,global}
                            Set the sharing mode.
      -D, --delete          Remove existing REST entities. This is a destructive
                            operation. In this mode, stanzas attributes are
                            unnecessary and therefore ignored. NOTE: This works
                            for 'local' entities only; the default folder cannot
                            be updated.



.. _ksconf_cli_unarchive:

ksconf unarchive
****************

 .. code-block:: none

    usage: ksconf unarchive [-h] [--dest DIR] [--app-name NAME]
                            [--default-dir DIR] [--exclude EXCLUDE] [--keep KEEP]
                            [--allow-local]
                            [--git-sanity-check {off,changed,untracked,ignored}]
                            [--git-mode {nochange,stage,commit}] [--no-edit]
                            [--git-commit-args GIT_COMMIT_ARGS]
                            SPL
    
    Install or overwrite an existing app in a git-friendly way.
    If the app already exist, steps will be taken to upgrade it safely.
    
    The 'default' folder can be redirected to another path (i.e., 'default.d/10-upstream' or
    whatever which is helpful if you're using the ksconf 'combine' mode.)
    
    positional arguments:
      SPL                   The path to the archive to install.
    
    optional arguments:
      -h, --help            show this help message and exit
      --dest DIR            Set the destination path where the archive will be
                            extracted. By default the current directory is used,
                            but sane values include etc/apps, etc/deployment-apps,
                            and so on.
      --app-name NAME       The app name to use when expanding the archive. By
                            default, the app name is taken from the archive as the
                            top-level path included in the archive (by
                            convention).
      --default-dir DIR     Name of the directory where the default contents will
                            be stored. This is a useful feature for apps that use
                            a dynamic default directory that's created and managed
                            by the 'combine' mode.
      --exclude EXCLUDE, -e EXCLUDE
                            Add a file pattern to exclude. Splunk's pseudo-glob
                            patterns are supported here. '*' for any non-directory
                            match, '...' for ANY (including directories), and '?'
                            for a single character.
      --keep KEEP, -k KEEP  Specify a pattern for files to preserve during an
                            upgrade. Repeat this argument to keep multiple
                            patterns.
      --allow-local         Allow local/* and local.meta files to be extracted
                            from the archive.
      --git-sanity-check {off,changed,untracked,ignored}
                            By default 'git status' is run on the destination
                            folder to detect working tree or index modifications
                            before the unarchive process start. Sanity check
                            choices go from least restrictive to most thorough:
                            'off' prevents all safely checks. 'changed' aborts
                            only upon local modifications to files tracked by git.
                            'untracked' (the default) looks for changed and
                            untracked files. 'ignored' aborts is (any) local
                            changes, untracked, or ignored files are found.
      --git-mode {nochange,stage,commit}
                            Set the desired level of git integration. The default
                            mode is *stage', where new, updated, or removed files
                            are automatically handled for you. To prevent any 'git
                            add' or 'git rm' commands from being run, pick the
                            'nochange' mode.
      --no-edit             Tell git to skip opening your editor. By default you
                            will be prompted to review/edit the commit message.
                            (Git Tip: Delete the content of the message to abort
                            the commit.)
      --git-commit-args GIT_COMMIT_ARGS, -G GIT_COMMIT_ARGS
                            Extra arguments to pass to 'git'


