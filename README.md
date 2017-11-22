# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
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


