---
name: Bug report
about: Report an issue or problem

---

# The problem

Briefly describe the issue you are experiencing.  Tell us what you were trying to do and what happened instead.  If you have a question, discard this template and please use the "question" label.

## Environment

* Ksconf version:  (Grab the first 2 text lines of output after running `ksconf --version`)
* OS & version used:
* Python version:
* Installed via:  (pip, git, Splunk app, or so on)

## Details

Describe the problem you have been experiencing in more detail.  Please include the command line arguments and output text.  A Traceback is especially useful (set `KSCONF_DEBUG=1` to enable more output).  Any steps you've take to troubleshoot or hints about what's wrong in the code can be very informative.

Wrap any output in triple backticks, like so:

```
$ ksconf --version
 _                             ___
| |                           / __)
| |  _  ___  ____ ___  ____ _| |__
| |_/ )/___)/ ___) _ \|  _ (_   __)
|  _ (|___ ( (__| |_| | | | || |
|_| \_|___/ \____)___/|_| |_||_|

ksconf 0.5.1.dev0+dirty  (Build None)
Git SHA1 17f6d94b committed on 2018-06-28
Written by Lowell Alleman <lowell@kintyre.co>.
Copyright (c) 2018 Kintyre Solutions, Inc.
Licensed under Apache Public License v2
```

Example Traceback:

```
Traceback (most recent call last):
  File "/opt/splunk/etc/apps/ksconf/bin/lib/ksconf/__main__.py", line 155, in cli
    return_code = args.funct(args)
  ...
  File "/opt/splunk/etc/apps/ksconf/bin/lib/ksconf/commands/restpublish.py", line 119, in connect_splunkd
    self._service = splunklib.client.connect(
AttributeError: 'NoneType' object has no attribute 'client'
```


## Steps To Reproduce Issue [ Good To Have ]

Please remember that sample configs often make problems easier to reproduce making it faster to fix the bug.

1. Step 1
2. Step 2
3. Step 3

