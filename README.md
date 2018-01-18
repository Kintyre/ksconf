# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
## kast.py
    usage: kast.py [-h] [-S MODE] [-K MODE] {combine,diff,patch,merge,sort} ...
    
    positional arguments:
      {combine,diff,patch,merge,sort}
        combine             Combine .conf settings from across multiple
                            directories into a single consolidated target
                            directory. This is similar to running 'merge'
                            recursively against a set of directories.
        diff                Compare two .conf files
        patch               Patch .conf settings from one file into another either
                            automatically (all changes) or interactively allowing
                            the user to pick which stanzas and keys to integrate
        merge               Merge two or more .conf files
        sort                Sort a Splunk .conf file
    
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
                      consitently.


### kast.py patch
    usage: kast.py patch [-h] [--target FILE] [--interactive] [--copy] FILE
    
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
      --copy                Copy settings from the source configuration file
                            instead of migrating the selected settings from the
                            source to the target, which is the default behavior if
                            the target is a file rather than standard out.


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


