#!/usr/bin/env python

import os
import sys
import re
import filecmp
from glob import glob
from subprocess import Popen, PIPE

def cmd_output(*cmd):
    p = Popen(cmd, stdout=PIPE, env={"PYTHONWARNINGS":"ignore"})
    p.wait()
    return p.stdout.readlines()

def parse_subcommand(lines):
    text = "\n".join(lines)
    match = re.search(r'[\r\n]+positional arguments:\s*\{([\w,-]+)\}', text)
    if match:
        subcommands = match.group(1).split(",")
        return subcommands
    return []

def prefix(iterable, indent=4):
    p = " " * indent
    for line in iterable:
        yield p + line

def write_doc_for(stream, script, level=2, *subcmds):
    subcmds = list(subcmds)
    args = [ sys.executable, script ] + subcmds + [ "--help" ]
    out = list(cmd_output(*args))
    stream.write("{} {}\n".format("#" * level, " ".join([script] + subcmds)))
    for line in prefix(out):
        stream.write(line)
    stream.write("\n\n")
    for subcmd in parse_subcommand(out):
        sc = subcmds + [ subcmd ]
        print "  Subcmd docs for {} {}".format(script, " ".join(sc))
        write_doc_for(stream, script, level+1, *sc)

readme = open("README.md.tmp", "w")
readme.write("""\
# Kintyre Splunk Configuration tool

[![Travis](https://img.shields.io/travis/Kintyre/ksconf.svg?style=plastic)](https://travis-ci.org/Kintyre/ksconf/builds)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)

Install with

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

The following documents the CLI options

""")


for script in glob("*.py"):
    if "make_cli_docs" in script:
        continue  # Don't fork bomb
    if "test" in script or script == "setup.py":
        continue
    print "Building docs for {}".format(script)
    write_doc_for(readme, script)

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
