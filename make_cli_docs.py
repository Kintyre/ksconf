#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import filecmp
import os
import re
import sys
from io import open
from subprocess import Popen, PIPE


def cmd_output(*cmd):
    p = Popen(cmd, stdout=PIPE, env={"PYTHONWARNINGS": "ignore", "PYTHONIOENCODING": "utf-8"})
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


def write_doc_for(stream, cmd, level=2, cmd_name=None, level_inc=1, *subcmds):
    subcmds = list(subcmds)
    if not cmd_name:
        cmd_name = str(cmd)
    if not isinstance(cmd, (list, tuple)):
        cmd = [cmd]
    args = [sys.executable] + cmd + subcmds + ["--help"]
    out = list(cmd_output(*args))
    stream.write("{} {}\n".format("#" * level, " ".join([cmd_name] + subcmds)))
    for line in prefix(out):
        stream.write(line + "\n")
    stream.write("\n\n")
    for subcmd in parse_subcommand(out):
        sc = subcmds + [subcmd]
        print("  Subcmd docs for {} {}".format(cmd_name, " ".join(sc)))
        write_doc_for(stream, cmd, level + level_inc, cmd_name, level_inc, *sc)


readme_file = os.path.join("docs", "source", "cli.md")
readme_file_tmp = readme_file + ".tmp"
readme = open(readme_file_tmp, "w", encoding="utf-8")
readme.write("""\
# Command line reference


The following documents the CLI options

""")

print("Building docs for ksconf")
write_doc_for(readme, ["-m", "ksconf.cli"], cmd_name="ksconf", level=2, level_inc=0)

readme.close()

if not os.path.isfile(readme_file):
    print("Make fresh {}".format(readme_file))
    os.rename(readme_file_tmp, readme_file)
    sys.exit(1)
if filecmp.cmp(readme_file_tmp, readme_file):
    print("No changes made to file.")
    os.unlink(readme_file_tmp)
    sys.exit(0)
else:
    print("{} updated".format(readme_file))
    os.unlink(readme_file)
    os.rename(readme_file_tmp, readme_file)
    sys.exit(1)
