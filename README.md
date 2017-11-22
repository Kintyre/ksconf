# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
## sort_conf.py
    usage: sort_conf.py [-h] [--inplace | --output FILE] [-n LINES]
                        FILE [FILE ...]
    
    positional arguments:
      FILE                  Input file to sort, or standard input.
    
    optional arguments:
      -h, --help            show this help message and exit
      --inplace, -i         Replace the input file with a sorted version. Warning
                            this a potentially destructive operation that may
                            move/remove comments.
      --output FILE, -o FILE
                            File to write results to. Defaults to stdout.
      -n LINES, --newlines LINES
                            Lines between stanzas.


