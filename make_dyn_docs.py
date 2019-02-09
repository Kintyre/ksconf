#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
import re
import sys
from subprocess import Popen, PIPE

# Prevent installed (likely older) version of ksconf from taking over
project_dir = os.path.dirname(os.path.abspath(__file__ or sys.argv[0]))
sys.path.insert(0, project_dir)

from ksconf.util.file import ReluctantWriter



def cmd_output(*cmd):
    p = Popen(cmd, stdout=PIPE, env={
        b"PYTHONWARNINGS": b"ignore",
        b"PYTHONIOENCODING": b"utf-8",
        b"KSCONF_DISABLE_PLUGINS": b"ksconf_cmd"})
    (stdout, stderr) = p.communicate()
    return stdout.decode("utf-8").splitlines()


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

def restructured_header(header, level):
    level_symbols= '#*=-^"~'
    char = level_symbols[level-1]
    return "{}\n{}\n".format(header, char * len(header))


def write_doc_for(stream, cmd, level=2, cmd_name=None, level_inc=1, *subcmds):
    subcmds = list(subcmds)
    if not cmd_name:
        cmd_name = str(cmd)
    if not isinstance(cmd, (list, tuple)):
        cmd = [cmd]
    args = [sys.executable] + cmd + subcmds + ["--help"]
    out = list(cmd_output(*args))
    heading = " ".join([cmd_name] + subcmds)
    ref = "_".join(["", cmd_name, "cli"] + subcmds)
    stream.write(".. {}:\n\n{}\n".format(ref, restructured_header(heading, level)))
    stream.write(" .. code-block:: none\n\n")
    for line in prefix(out):
        stream.write(line + "\n")
    stream.write("\n\n\n")
    for subcmd in parse_subcommand(out):
        sc = subcmds + [subcmd]
        print("  Subcmd docs for {} {}".format(cmd_name, " ".join(sc)))
        write_doc_for(stream, cmd, level + level_inc, cmd_name, level_inc, *sc)


readme_file = os.path.join(project_dir, "docs", "source", "dyn", "cli.rst")
readme = ReluctantWriter(readme_file, "w", newline="\n", encoding="utf-8")

with readme as stream:
    stream.write(restructured_header("Command line reference", 1))
    stream.write("\n\nKSCONF supports the following CLI options:\n\n")
    print("Building docs for ksconf")
    write_doc_for(stream, ["-m", "ksconf"], cmd_name="ksconf", level=2, level_inc=0)

if readme.result == "created":
    print("Make fresh {}".format(readme_file))
elif readme.result == "unchanged":
    print("No changes made to file.")
elif readme.result == "updated":
    print("{} updated".format(readme_file))

# Return a non-0 exit code to tell pre-commit that changes were made (abort current commit session)
if readme.change_needed:
    sys.exit(1)
