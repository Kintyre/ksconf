# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
## ksconf.py
    usage: ksconf.py [-h] [-S MODE] [-K MODE]
                     {check,combine,diff,promote,merge,minimize,sort,unarchive}
                     ...
    
    Kintyre Splunk CONFig tool.
    
    This utility handles a number of common Splunk app maintenance tasks in a small
    and easy to relocate package.  Specifically, this tools deals with many of the
    nuances with storing Splunk apps in git, and pointing live Splunk apps to a git
    repository.  Merging changes from the live system's (local) folder to the
    version controlled (default) folder, and dealing with more than one layer of 
    "default" (which splunk can't handle natively) are all supported tasks.
    
    positional arguments:
      {check,combine,diff,promote,merge,minimize,sort,unarchive}
        check               Perform a basic syntax and sanity check on .conf files
        combine             Combine .conf settings from across multiple
                            directories into a single consolidated target
                            directory. This is similar to running 'merge'
                            recursively against a set of directories.
        diff                Compares settings differences of two .conf files. This
                            command ignores textual differences (like order,
                            spacing, and comments) and focuses strictly on
                            comparing stanzas, keys, and values. Note that spaces
                            within any given value will be compared.
        promote             Promote .conf settings from one file into another
                            either in batch mode (all changes) or interactively
                            allowing the user to pick which stanzas and keys to
                            integrate. This can be used to push changes made via
                            the UI, whichare stored in a 'local' file, to the
                            version-controlled 'default' file. Note that the
                            normal operation moves changes from the SOURCE file to
                            the TARGET, updating both files in the process. But
                            it's also possible to preserve the local file, if
                            desired.
        merge               Merge two or more .conf files
        minimize            Minimize the target file by removing entries
                            duplicated in the default conf(s) provided.
        sort                Sort a Splunk .conf file
        unarchive           Install or overwrite an existing app in a git-friendly
                            way. If the app already exist, steps will be taken to
                            upgrade it in a sane way.
    
    optional arguments:
      -h, --help            show this help message and exit
      -S MODE, --duplicate-stanza MODE
                            Set duplicate stanza handling mode. If [stanza] exists
                            more than once in a single .conf file: Mode
                            'overwrite' will keep the last stanza found. Mode
                            'merge' will merge keys from across all stanzas,
                            keeping the the value form the latest key. Mode
                            'exception' (default) will abort if duplicate stanzas
                            are found.
      -K MODE, --duplicate-key MODE
                            Set duplicate key handling mode. A duplicate key is a
                            condition that occurs when the same key (key=value) is
                            set within the same stanza. Mode of 'overwrite'
                            silently ignore duplicate keys, keeping the latest.
                            Mode 'exception', the default, aborts if duplicate
                            keys are found.


### ksconf.py check
    usage: ksconf.py check [-h] FILE [FILE ...]
    
    positional arguments:
      FILE        One or more configuration files to check. If the special value
                  of '-' is given, then the list of files to validate is read from
                  standard input
    
    optional arguments:
      -h, --help  show this help message and exit


### ksconf.py combine
    usage: ksconf.py combine [-h] [--target TARGET] source [source ...]
    
    Common use case: ksconf combine default.d/* --target=default
    
    positional arguments:
      source                The source directory where configuration files will be
                            merged from. When multiple sources directories are
                            provided, start with the most general and end with the
                            specific; later sources will override values from the
                            earlier ones. Supports wildcards so a typical Unix
                            conf.d/##-NAME directory structure works well.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target TARGET, -t TARGET
                            Directory where the merged files will be stored.
                            Typically either 'default' or 'local'


### ksconf.py diff
    usage: ksconf.py diff [-h] [-o FILE] [--comments] FILE FILE
    
    positional arguments:
      FILE                  Left side of the comparison
      FILE                  Right side of the comparison
    
    optional arguments:
      -h, --help            show this help message and exit
      -o FILE, --output FILE
                            File where difference is stored. Defaults to standard
                            out.
      --comments, -C        Enable comparison of comments. (Unlikely to work
                            consistently)


### ksconf.py promote
    usage: ksconf.py promote [-h] [--batch | --interactive] [--force] [--keep]
                             [--keep-empty KEEP_EMPTY]
                             SOURCE TARGET
    
    The promote sub command is used to propigate .conf settings applied in one
    file (typically local) to another (typically default) This can be done in two
    different modes: In batch mode (all changes) or interactively allowing the
    user to pick which stanzas and keys to integrate. This can be used to push
    changes made via the UI, which are stored in a 'local' file, to the version-
    controlled 'default' file. Note that the normal operation moves changes from
    the SOURCE file to the TARGET, updating both files in the process. But it's
    also possible to preserve the local file, if desired.
    
    positional arguments:
      SOURCE                The source configuration file to pull changes from.
                            (Typically the 'local' conf file)
      TARGET                Configuration file or directory to push the changes
                            into. (Typically the 'default' folder) When a
                            directory is given instead of a file then the same
                            file name is assumed for both SOURCE and TARGET
    
    optional arguments:
      -h, --help            show this help message and exit
      --batch, -b           Use batch mode where all configuration settings are
                            automatically promoted. All changes are moved from the
                            source to the target file and the source file will be
                            blanked or removed.
      --interactive, -i     Enable interactive mode where the user will be
                            prompted to approve the promotion of specific stanzas
                            and keys. The user will be able to apply, skip, or
                            edit the changes being promoted. (This functionality
                            was inspired by 'git add --patch').
      --force, -f           Disable safety checks.
      --keep, -k            Keep conf settings in the source file. This means that
                            changes will be copied into the target file instead of
                            moved there.
      --keep-empty KEEP_EMPTY
                            Keep the source file, even if after the settings
                            promotions the file has no content. By default, SOURCE
                            will be removed if all content has been moved into the
                            TARGET location. Splunk will re-create any necessary
                            local files on the fly.


### ksconf.py merge
    usage: ksconf.py merge [-h] [--target FILE] FILE [FILE ...]
    
    positional arguments:
      FILE                  The source configuration file to pull changes from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            Save the merged configuration files to this target
                            file. If not given, the default is to write the merged
                            conf to standard output.


### ksconf.py minimize
    usage: ksconf.py minimize [-h] [--target FILE] [--output OUTPUT]
                              [-k PRESERVE_KEY]
                              FILE [FILE ...]
    
    The minimize command will allow for the removal of all default-ish settings
    from a target configuration files. In theory, this allows for a cleaner
    upgrade, and fewer duplicate settings.
    
    positional arguments:
      FILE                  The default configuration file(s) used to determine
                            what base settings are unncessary to keep in the
                            target file.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            This is the local file that you with to remove the
                            duplicate settings from. By default, this file will be
                            read and the updatedwith a minimized version.
      --output OUTPUT       When this option is used, the new minimized file will
                            be saved to this file instead of updating TARGET. This
                            can be use to preview changes or helpful in other
                            workflows.
      -k PRESERVE_KEY, --preserve-key PRESERVE_KEY
                            Specify a key that should be allowed to be a
                            duplication but should be preserved within the
                            minimized output. For example the it'soften desirable
                            keep the 'disabled' settings in the local file, even
                            if it's enabled by default.


### ksconf.py sort
    usage: ksconf.py sort [-h] [--target FILE | --inplace] [-n LINES]
                          FILE [FILE ...]
    
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


### ksconf.py unarchive
    usage: ksconf.py unarchive [-h] [--dest DIR] [--app-name NAME]
                               [--default-dir DIR]
                               [--git-sanity-check {all,disable,changes,untracked}]
                               SPL
    
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
                            top-level path included in the archive (by convention)
                            Expanding archives that contain multiple (ITSI) or
                            nested apps (NIX, ES) is not supported.
      --default-dir DIR     Name of the directory where the default contents will
                            be stored. This is a useful feature for apps that use
                            a dynamic default directory that's created by the
                            'combine' mode.
      --git-sanity-check {all,disable,changes,untracked}
                            By default a 'git status' is run on the destination
                            folder to see if the working tree has any
                            modifications before the unarchive process starts.
                            (This check is automatically disabled if git is not in
                            use or not installed.)


