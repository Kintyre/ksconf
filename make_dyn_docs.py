#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
import re
import sys
from subprocess import Popen, PIPE
from functools import wraps

from six import PY2

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
    level_symbols = '#*=-^"~'
    char = level_symbols[level - 1]
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


def show_changes(f):
    @wraps(f)
    def wrapper(path):
        rw = f(path)
        if rw.result == "created":
            print("Make fresh {}".format(path))
        elif rw.result == "unchanged":
            print("No changes made to {}.".format(path))
        elif rw.result == "updated":
            print("{} updated".format(path))
        if rw.change_needed:
            return 1
        return 0
    return wrapper


@show_changes
def make_cli_docs(readme_file):
    readme = ReluctantWriter(readme_file, "w", newline="\n", encoding="utf-8")
    with readme as stream:
        stream.write(restructured_header("Command line reference", 1))
        stream.write("\n\nKSCONF supports the following CLI options:\n\n")
        print("Building docs for ksconf")
        write_doc_for(stream, ["-m", "ksconf"], cmd_name="ksconf", level=2, level_inc=0)
    return readme



@show_changes
def make_subcommands_table(csv_path):
    import csv
    from ksconf.commands import get_entrypoints
    if PY2:
        table = ReluctantWriter(csv_path, "wb")
    else:
        table = ReluctantWriter(csv_path, "w", encoding="utf-8")
    with table as stream:
        csvwriter = csv.writer(stream, dialect=csv.QUOTE_NONNUMERIC)
        for (name, entry) in get_entrypoints("ksconf_cmd").items():
            # Pros/conf links to the doc vs 'ref'?
            #ref_template = ":doc:`cmd_{}`"
            ref_template = ":ref:`ksconf {0} <ksconf_cmd_{0}>`"
            cmd_cls = entry.load()
            row = [
                ref_template.format(name),
                cmd_cls.maturity,
                cmd_cls.help.replace("\n", " "),
            ]
            # Workaround csv module not supporting unicode in PY2
            if PY2:
                row = [ s.encode("utf-8") for s in row ]
            csvwriter.writerow(row)
    return table


if __name__ == '__main__':
    docs_dir = lambda filename: os.path.join(project_dir, "docs", "source", "dyn", filename)
    changes = 0

    changes += make_cli_docs(docs_dir("cli.rst"))
    changes += make_subcommands_table(docs_dir("ksconf_subcommands.csv"))

    # Return a non-0 exit code to tell pre-commit that changes were made (abort current commit session)
    if changes:
        sys.exit(1)
