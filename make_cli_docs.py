#!/usr/bin/env python

import os
import sys
import filecmp
from glob import glob
from subprocess import Popen, PIPE

def cmd_output(*cmd):
    p = Popen(cmd, stdout=PIPE, env={"PYTHONWARNINGS":"ignore"})
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

readme = open("README.md.tmp", "w")
readme.write("""\
# Kintyre Splunk Configuration tool


Install with

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

The following documents the CLI options

""")

subcommands = {
    "ksconf.py" :
        [ "check", "combine", "diff", "promote" ,"merge", "minimize", "sort", "unarchive" ],
}

for script in glob("*.py"):
    if "make_cli_docs" in script:
        continue  # Don't fork bomb
    if script.startswith("test_") or script == "setup.py":
        continue
    print "Building docs for {}".format(script)
    write_doc_for(readme, script)
    for subcmds in subcommands.get(script, []):
        print "  Subcmd docs for {} {}".format(script, subcmds)
        write_doc_for(readme, script, *subcmds.split(" "))

readme.close()

if not os.path.isfile("README.md"):
    print "Make fresh README.md"
    os.rename("README.md.tmp", "README.md")
    sys.exit(1)
if filecmp.cmp("README.md.tmp", "README.md"):
    print "No changes made to file."
    os.unlink("README.md.tmp")
    sys.exit(0)
else:
    print "README.md updated"
    os.unlink("README.md")
    os.rename("README.md.tmp", "README.md")
    sys.exit(1)
