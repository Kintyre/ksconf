#!/usr/bin/env python

import os
import sys
import re
import filecmp
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

def write_doc_for(stream, cmd, level=2, cmd_name=None, *subcmds):
    subcmds = list(subcmds)
    if not cmd_name:
        cmd_name = str(cmd)
    if not isinstance(cmd, (list, tuple)):
        cmd = [ cmd ]
    args = [ sys.executable ] + cmd + subcmds + [ "--help" ]
    out = list(cmd_output(*args))
    stream.write("{} {}\n".format("#" * level, " ".join([cmd_name] + subcmds)))
    for line in prefix(out):
        stream.write(line)
    stream.write("\n\n")
    for subcmd in parse_subcommand(out):
        sc = subcmds + [ subcmd ]
        print "  Subcmd docs for {} {}".format(cmd_name, " ".join(sc))
        write_doc_for(stream, cmd, level+1, cmd_name, *sc)

readme = open("README.md.tmp", "w")
readme.write("""\
# Kintyre Splunk Configuration tool

[![Travis](https://img.shields.io/travis/Kintyre/ksconf.svg)](https://travis-ci.org/Kintyre/ksconf/builds)
[![codecov](https://codecov.io/gh/Kintyre/ksconf/branch/master/graph/badge.svg)](https://codecov.io/gh/Kintyre/ksconf)
[![Coverage Status](https://coveralls.io/repos/github/Kintyre/ksconf/badge.svg?branch=master)](https://coveralls.io/github/Kintyre/ksconf?branch=master)
[![Windows Build status](https://ci.appveyor.com/api/projects/status/rlbgstkpf17y8nxh?svg=true)](https://ci.appveyor.com/project/lowell80/ksconf)


Install with

    git clone https://github.com/Kintyre/ksconf.git
    cd ksconf
    pip install .

Confirm installation with the following command:

    ksconf --help

The following documents the CLI options

""")

print "Building docs for ksconf"
write_doc_for(readme, ["-m", "ksconf.cli"], cmd_name="ksconf")


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
