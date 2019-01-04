# Command line reference


The following documents the CLI options

## ksconf
    usage: ksconf [-h] [--version] [--force-color]
                  {check,combine,diff,promote,merge,minimize,sort,rest-export,unarchive}
                  ...
    
    Ksconf: Kintyre Splunk CONFig tool
    
    This utility handles a number of common Splunk app maintenance tasks in a small
    and easy to deploy package.  Specifically, this tools deals with many of the
    nuances with storing Splunk apps in git, and pointing live Splunk apps to a git
    repository.  Merging changes from the live system's (local) folder to the
    version controlled (default) folder, and dealing with more than one layer of
    "default" (which splunk can't handle natively) are all supported tasks.
    
    positional arguments:
      {check,combine,diff,promote,merge,minimize,sort,rest-export,unarchive}
        check               Perform basic syntax and sanity checks on .conf files
        combine             Combine configuration files across multiple source
                            directories into a single destination directory. This
                            allows for an arbitrary number of splunk configuration
                            layers to coexist within a single app. Useful in both
                            ongoing merge and one-time ad-hoc use. For example,
                            combine can consolidate 'users' directory across
                            several instances after a phased server migration.
        diff                Compare settings differences between two .conf files
                            ignoring spacing and sort order
        promote             Promote .conf settings from one file into another
                            either in batch mode (all changes) or interactively
                            allowing the user to pick which stanzas and keys to
                            integrate. Changes made via the UI (stored in the
                            local folder) can be promoted (moved) to a version-
                            controlled directory.
        merge               Merge two or more .conf files
        minimize            Minimize the target file by removing entries
                            duplicated in the default conf(s)
        sort                Sort a Splunk .conf file creating a normalized format
                            appropriate for version control
        rest-export         Export .conf settings as a curl script to apply to a
                            Splunk instance later (via REST)
        unarchive           Install or upgrade an existing app in a git-friendly
                            and safe way
    
    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      --force-color         Force TTY color mode on. Useful if piping the output a
                            color-aware pager, like 'less -R'


## ksconf check
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


## ksconf combine
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
    
    THE PROBLEM:
    
    In a typical enterprise deployment of Splunk, a single app can easily have
    multiple logical sources of configuration:  (1) The upstream app developer, (2)
    local developer app-developer adds organization-specific customizations or
    fixes, (3) splunk admin tweaks the inappropriate 'indexes.conf' settings, and
    (4) custom knowledge objects added by your subject matter experts.  Ideally we'd
    like to version control these, but doing so is complicated because normally you
    have to manage all 4 of these logical layers in one 'default' folder.  (Splunk
    requires that app settings be located either in 'default' or 'local'; and
    managing local files with version control leads to merge conflicts; so
    effectively, all version controlled settings need to be in 'default', or risk
    merge conflicts.)  So when a new upstream version is released, someone has to
    manually upgrade the app being careful to preserve all custom configurations.
    The solution provided by the 'combine' functionality is that all of these
    logical sources can be stored separately in their own physical directories
    allowing changes to be managed independently.  (This also allows for different
    layers to be mixed-and-matched by selectively including which layers to
    combine.)  While this doesn't completely remove the need for a human to review
    app upgrades, it does lower the overhead enough that updates can be pulled in
    more frequently, thus reducing the divergence potential.  (Merge frequently.)
    
    NOTES:
    
    The 'combine' command is similar to running the 'merge' subcommand recursively
    against a set of directories.  One key difference is that this command will
    gracefully handle non-conf files intelligently too.
    
    EXAMPLE:
    
        Splunk_CiscoSecuritySuite/
        ├── README
        ├── default.d
        │   ├── 10-upstream
        │   │   ├── app.conf
        │   │   ├── data
        │   │   │   └── ui
        │   │   │       ├── nav
        │   │   │       │   └── default.xml
        │   │   │       └── views
        │   │   │           ├── authentication_metrics.xml
        │   │   │           ├── cisco_security_overview.xml
        │   │   │           ├── getting_started.xml
        │   │   │           ├── search_ip_profile.xml
        │   │   │           ├── upgrading.xml
        │   │   │           └── user_tracking.xml
        │   │   ├── eventtypes.conf
        │   │   ├── macros.conf
        │   │   ├── savedsearches.conf
        │   │   └── transforms.conf
        │   ├── 20-my-org
        │   │   └── savedsearches.conf
        │   ├── 50-splunk-admin
        │   │   ├── indexes.conf
        │   │   ├── macros.conf
        │   │   └── transforms.conf
        │   └── 70-firewall-admins
        │       ├── data
        │       │   └── ui
        │       │       └── views
        │       │           ├── attacks_noc_bigscreen.xml
        │       │           ├── device_health.xml
        │       │           └── user_tracking.xml
        │       └── eventtypes.conf
    
    Commands:
    
        cd Splunk_CiscoSecuritySuite
        ksconf combine default.d/* --target=default
    
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


## ksconf diff
    usage: ksconf diff [-h] [-o FILE] [--comments] CONF1 CONF2
    
    Compares the content differences of two .conf files
    
    This command ignores textual differences (like order, spacing, and comments) and
    focuses strictly on comparing stanzas, keys, and values.  Note that spaces
    within any given value will be compared.  Multiline fields are compared in are
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


## ksconf promote
    usage: ksconf promote [-h] [--batch | --interactive] [--force] [--keep]
                          [--keep-empty]
                          SOURCE TARGET
    
    Propagate .conf settings applied in one file to another.  Typically this is used
    to take local changes made via the UI and push them into a default (or
    default.d/) location.
    
    NOTICE:  By default, changes are *MOVED*, not just copied.
    
    Promote has two different modes:  batch and interactive.  In batch mode all
    changes are applied automatically and the (now empty) source file is removed.
    In interactive mode the user is prompted to pick which stanzas and keys to
    integrate.  This can be used to push  changes made via the UI, which are stored
    in a 'local' file, to the version-controlled 'default' file.  Note that the
    normal operation moves changes from the SOURCE file to the TARGET, updating both
    files in the process.  But it's also possible to preserve the local file, if
    desired.
    
    If either the source file or target file is modified while a promotion is under
    progress, changes will be aborted.  And any custom selections you made will be
    lost.  (This needs improvement.)
    
    positional arguments:
      SOURCE             The source configuration file to pull changes from.
                         (Typically the 'local' conf file)
      TARGET             Configuration file or directory to push the changes into.
                         (Typically the 'default' folder) As a shortcut, a
                         directory is given, then it's assumed that the same
                         basename is used for both SOURCE and TARGET. In fact, if
                         different basename as provided, a warning is issued.
    
    optional arguments:
      -h, --help         show this help message and exit
      --batch, -b        Use batch mode where all configuration settings are
                         automatically promoted. All changes are removed from
                         source and applied to target. The source file will be
                         removed, unless '--keep-empty' is used.
      --interactive, -i  Enable interactive mode where the user will be prompted
                         to approve the promotion of specific stanzas and keys.
                         The user will be able to apply, skip, or edit the changes
                         being promoted. (This functionality was inspired by 'git
                         add --patch').
      --force, -f        Disable safety checks.
      --keep, -k         Keep conf settings in the source file. All changes will
                         be copied into the target file instead of being moved
                         there. This is typically a bad idea since local always
                         overrides default.
      --keep-empty       Keep the source file, even if after the settings
                         promotions the file has no content. By default, SOURCE
                         will be removed after all content has been moved into
                         TARGET. Splunk will re-create any necessary local files
                         on the fly.


## ksconf merge
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
                            file. If not provided. the the merged conf is written
                            to standard output.
      --dry-run, -D         Enable dry-run mode. Instead of writing to TARGET,
                            preview changes in 'diff' format. If TARGET doesn't
                            exist, then show the merged file.
      --banner BANNER, -b BANNER
                            A banner or warning comment added to the top of the
                            TARGET file. This is often used to warn Splunk admins
                            from editing an auto-generated file.


## ksconf minimize
    usage: ksconf minimize [-h] [--target FILE] [--dry-run | --output OUTPUT]
                           [--explode-default] [-k PRESERVE_KEY]
                           FILE [FILE ...]
    
    Minimize a conf file by removing the default settings
    
    Reduce local conf file to only your indented changes without manually tracking
    which entries you've edited.  Minimizing local conf files makes your local
    customizations easier to read and often results in cleaner add-on upgrades.
    
    A typical scenario & why does this matter:
    
    To customizing a Splunk app or add-on, start by copying the conf file from
    default to local and then applying your changes to the local file.  That's good.
    But stopping here may complicated future upgrades, because the local file
    doesn't contain *just* your settings, it contains all the default settings too.
    Fixes published by the app creator may be masked by your local settings.  A
    better approach is to reduce the local conf file leaving only the stanzas and
    settings that you indented to change.  This make your conf files easier to read
    and makes upgrades easier, but it's tedious to do by hand.
    
    For special cases, the '--explode-default' mode reduces duplication between
    entries normal stanzas and global/default entries.  If 'disabled = 0' is a
    global default, it's technically safe to remove that setting from individual
    stanzas.  But sometimes it's preferable to be explicit, and this behavior may be
    too heavy-handed for general use so it's off by default.  Use this mode if your
    conf file that's been fully-expanded.  (i.e., conf entries downloaded via REST,
    or the output of "btool list").  This isn't perfect, since many apps push their
    settings into the global namespace, but it can help.
    
    Example usage:
    
        cd Splunk_TA_nix
        cp default/inputs.conf local/inputs.conf
    
        # Edit 'disabled' and 'interval' settings in-place
        vi local/inputs.conf
    
        # Remove all the extra (unmodified) bits
        ksconf minimize --target=local/inputs.conf default/inputs.conf
    
    positional arguments:
      FILE                  The default configuration file(s) used to determine
                            what base settings are " unnecessary to keep in the
                            target file.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            This is the local file that you with to remove the
                            duplicate settings from. By default, this file will be
                            read and the updated with a minimized version.
      --dry-run, -D         Enable dry-run mode. Instead of writing the minimizing
                            the TARGET file, preview what what be removed in the
                            form of a 'diff'.
      --output OUTPUT       Write the minimized output to a separate file instead
                            of updating TARGET. This can be use to preview changes
                            if dry-run produces a large diff. This may also be
                            helpful in other workflows.
      --explode-default, -E
                            Enable minimization across stanzas as well as files
                            for special use-cases. This mode will not only
                            minimize the same stanza across multiple config files,
                            it will also attempt to minimize default any values
                            stored in the [default] or global stanza as well.
                            Example: Trim out cruft in savedsearches.conf by
                            pointing to etc/system/default/savedsearches.conf
      -k PRESERVE_KEY, --preserve-key PRESERVE_KEY
                            Specify a key that should be allowed to be a
                            duplication but should be preserved within the
                            minimized output. For example, it may be desirable
                            keep the 'disabled' settings in the local file, even
                            if it's enabled by default.


## ksconf sort
    usage: ksconf sort [-h] [--target FILE | --inplace] [-F] [-q] [-n LINES]
                       FILE [FILE ...]
    
    Sort a Splunk .conf file.  Sort has two modes:  (1) by default, the sorted
    config file will be echoed to the screen.  (2) the config files are updated
    inplace when the '-i' option is used.
    
    Manually managed conf files can be blacklisted by add a comment containing the
    string 'KSCONF-NO-SORT' to the top of any .conf file.
    
    To recursively sort all files:
    
        find . -name '*.conf' | xargs ksconf sort -i
    
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


## ksconf rest-export
    usage: ksconf rest-export [-h] [--output FILE] [-u] [--url URL] [--app APP]
                              [--user USER]
                              FILE [FILE ...]
    
    Build an executable script of the stanzas in a configuration file that can be later applied to
    a running Splunk instance via the Splunkd REST endpoint.
    
    This can be helpful when pushing complex props & transforms to an instance where you only have
    UI access and can't directly publish an app.
    
    WARNING:  This command is indented for manual admin workflows.  It's quite possible that shell
    escaping bugs exist that may allow full shell access if you put this into an automated workflow.
    Evalute the risks, review the code, and run as a least-privilege user, and be responsible.
    
    For now the assumption is that 'curl' command will be used.  (Patches to support the Power Shell
    Invoke-WebRequest cmdlet would be greatly welcomed!)
    
    ksconf rest-export --output=apply_props.sh etc/app/Splunk_TA_aws/local/props.conf
    
    positional arguments:
      FILE                  Configuration file(s) to export settings from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --output FILE, -t FILE
                            Save the shell script output to this file. If not
                            provided, the output is written to standard output.
      -u, --update          Assume that the REST entities already exist. By
                            default output assumes stanzas are being created.
                            (This is an unfortunate quark of the configs REST API)
      --url URL             URL of Splunkd. Default: https://localhost:8089
      --app APP             Set the namespace (app name) for the endpoint
      --user USER           Set the user associated. Typically the default of
                            'nobody' is ideal if you want to share the
                            configurations at the app-level.


## ksconf unarchive
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
    
    Supports tarballs (.tar.gz, .spl), and less-common zip files (.zip)
    
    positional arguments:
      SPL                   The path to the archive to install.
    
    optional arguments:
      -h, --help            show this help message and exit
      --dest DIR            Set the destination path where the archive will be
                            extracted. By default the current directory is used,
                            but sane values include etc/apps, etc/deployment-apps,
                            and so on. This could also be a git repository working
                            tree where splunk apps are stored.
      --app-name NAME       The app name to use when expanding the archive. By
                            default, the app name is taken from the archive as the
                            top-level path included in the archive (by
                            convention). Expanding archives that contain multiple
                            (ITSI) or nested apps (NIX, ES) is not supported.)
      --default-dir DIR     Name of the directory where the default contents will
                            be stored. This is a useful feature for apps that use
                            a dynamic default directory that's created and managed
                            by the 'combine' mode.
      --exclude EXCLUDE, -e EXCLUDE
                            Add a file pattern to exclude. Splunk's psudo-glob
                            patterns are supported here. '*' for any non-directory
                            match, '...' for ANY (including directories), and '?'
                            for a single character.
      --keep KEEP, -k KEEP  Specify a pattern for files to preserve during an
                            upgrade. Repeat this argument to keep multiple
                            patterns.
      --allow-local         Allow local/ and local.meta files to be extracted from
                            the archive. Shipping local files is a Splunk app
                            packaging violation so local files are blocked to
                            prevent content from being overridden.
      --git-sanity-check {off,changed,untracked,ignored}
                            By default 'git status' is run on the destination
                            folder to detect working tree or index modifications
                            before the unarchive process starts, but this is
                            configurable. Sanity check choices go from least
                            restrictive to most thorough: Use 'off' to prevent any
                            'git status' safely checks. Use 'changed' to abort
                            only upon local modifications to files tracked by git.
                            Use 'untracked' (the default) to look for changed and
                            untracked files before considering the tree clean. Use
                            'ignored' to enable the most intense safety check
                            which will abort if local changes, untracked, or
                            ignored files are found. NOTE: Sanity checks are
                            automatically disabled if the app is not in a git
                            working tree, or git is not installed.
      --git-mode {nochange,stage,commit}
                            Set the desired level of git integration. The default
                            mode is 'stage', where new, updated, or removed files
                            are automatically handled for you. If 'commit' mode is
                            selected, then files are committed with an auto-
                            generated commit message. To prevent any 'git add' or
                            'git rm' commands from being run, pick the 'nochange'
                            mode. Notes: (1) The git mode is irrelevant if the app
                            is not in a git working tree. (2) If a git commit is
                            incorrect, simply roll it back with 'git reset' or fix
                            it with a 'git commit --amend' before the changes are
                            pushed anywhere else. (That's why you're using git in
                            the first place, right?)
      --no-edit             Tell git to skip opening your editor. By default you
                            will be prompted to review/edit the commit message.
                            (Git Tip: Delete the content of the message to abort
                            the commit.)
      --git-commit-args GIT_COMMIT_ARGS, -G GIT_COMMIT_ARGS


