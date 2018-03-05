# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
## kast.py
    usage: kast.py [-h] [-S MODE] [-K MODE]
                   {check,combine,diff,patch,merge,minimize,sort,unarchive} ...
    
    positional arguments:
      {check,combine,diff,patch,merge,minimize,sort,unarchive}
        check               Perform a basic syntax and sanity check on .conf files
        combine             Combine .conf settings from across multiple
                            directories into a single consolidated target
                            directory. This is similar to running 'merge'
                            recursively against a set of directories.
        diff                Compares settings differences of two .conf files. This
                            command ignores textual differences (like order,
                            spacing, and comments) and focuses strictly on
                            comparing stanzas, keys, and values.
        patch               Patch .conf settings from one file into another either
                            automatically (all changes) or interactively allowing
                            the user to pick which stanzas and keys to integrate
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


### kast.py check
    usage: kast.py check [-h] FILE [FILE ...]
    
    positional arguments:
      FILE        One or more configuration files to check. If the special value
                  of '-' is given, then the list of files to validate is read from
                  standard input
    
    optional arguments:
      -h, --help  show this help message and exit


### kast.py combine
    usage: kast.py combine [-h]
    
    optional arguments:
      -h, --help  show this help message and exit


### kast.py diff
    usage: kast.py diff [-h] [--comments] FILE FILE
    
    positional arguments:
      FILE            Left side of the comparison
      FILE            Right side of the comparison
    
    optional arguments:
      -h, --help      show this help message and exit
      --comments, -C  Enable comparison of comments. (Unlikely to work
                      consistently.


### kast.py patch
    usage: kast.py patch [-h] [--target FILE] [--interactive] FILE
    
    positional arguments:
      FILE                  The source configuration file to pull changes from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            Save the merged configuration files to this target
                            file. If not given, the default is to write the merged
                            conf to standard output.
      --interactive, -i     Enable interactive mode (like git '--patch' or add
                            '-i' mode.)


### kast.py merge
    usage: kast.py merge [-h] [--target FILE] FILE [FILE ...]
    
    positional arguments:
      FILE                  The source configuration file to pull changes from.
    
    optional arguments:
      -h, --help            show this help message and exit
      --target FILE, -t FILE
                            Save the merged configuration files to this target
                            file. If not given, the default is to write the merged
                            conf to standard output.


### kast.py minimize
    usage: kast.py minimize [-h]
    
    optional arguments:
      -h, --help  show this help message and exit


### kast.py sort
    usage: kast.py sort [-h] [--target FILE | --inplace] [-n LINES]
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


### kast.py unarchive
    usage: kast.py unarchive [-h] [--dest DIR] [--app-name NAME]
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


## sort_conf.py
    usage: sort_conf.py [-h] [--inplace | --output FILE] [-n LINES] [-S MODE]
                        [-K MODE]
                        FILE [FILE ...]
    
    positional arguments:
      FILE                  Input file to sort, or standard input.
    
    optional arguments:
      -h, --help            show this help message and exit
      --inplace, -i         Replace the input file with a sorted version. Warning
                            this a potentially destructive operation that may
                            move/remove comments.
      --output FILE, -o FILE
                            File to write results to. Defaults to standard output.
      -n LINES, --newlines LINES
                            Lines between stanzas.
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


