#!/usr/bin/env python

import os
import sys
from glob import glob
from subprocess import Popen, PIPE

def cmd_output(*cmd):
    p = Popen(cmd, stdout=PIPE)
    p.wait()
    for line in p.stdout.readlines():
        yield line

def prefix(iterable, indent=4):
    p = " " * indent
    for line in iterable:
        yield p + line

def write_doc_for(stream, script, *subcmds):
    level = 2 + len(subcmds)
    subcmds = list(subcmds)
    args = [ sys.executable, script ] + subcmds + [ "--help" ]
    #args.extend(list(subcmds))
    #args.append("--help")
    out = cmd_output(*args)
    stream.write("{} {}\n".format("#" * level, " ".join([script] + subcmds)))
    for line in prefix(out):
        stream.write(line)
    stream.write("\n\n")

readme = open("README.md", "w")
readme.write("""\
# Kintyre Splunk Admin Script with CLI interfaces
Kintyre's Splunk scripts for various admin tasks.
""")

subcommands = {
    "ksconf.py" : 
        [ "check", "combine", "diff", "promote" ,"merge", "minimize", "sort", "unarchive"]
}

for script in glob("*.py"):
    if "make_cli_docs" in script:
        continue  # Don't fork bomb
    print "Building docs for {}".format(script)
    write_doc_for(readme, script)
    for subcmds in subcommands.get(script, []):
        print "  Subcmd docs for {} {}".format(script, subcmds)
        write_doc_for(readme, script, *subcmds.split(" "))

readme.close()

