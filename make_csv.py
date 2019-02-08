
import csv
from ksconf.commands import get_entrypoints


def unwrap(s):
    return s.replace("\n", " ")

def build_csv(out_file):

    with open(out_file, "w") as stream:
        csvwriter = csv.writer(stream, dialect=csv.QUOTE_ALL)
        # XXX: Should refactor?   Borrowed from ksconf/__main__.py

        for (name, entry) in get_entrypoints("ksconf_cmd").items():
            # Pros/conf links to the doc vs 'ref'?
            #ref_template = ":doc:`cmd_{}`"
            ref_template = ":ref:`ksconf {0} <ksconf_cmd_{0}>`"
            cmd_cls = entry.load()
            row = [ ref_template.format(name), cmd_cls.maturity, unwrap(cmd_cls.help) ]
            csvwriter.writerow( row)



if __name__ == '__main__':
    build_csv("docs/source/dyn/ksconf_subcommands.csv")
