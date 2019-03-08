#!/usr/bin/env python

import csv
import sys
import os
from optparse import OptionParser
from decimal import Decimal, InvalidOperation

parser = OptionParser(usage="usage:  %prog [options] file.csv [file2.csv] ...",
                      description="This utility sorts CSV file(s) with consistent quoting.")

parser.add_option("-i", "--in-place",
                  action="store_true",
                  help="Modify the existing '.csv' file inplace "
                  "(Default: create a new output file with a '.new' extension)")
parser.add_option("-d", "--delimiter", action="store", default=",", metavar="CHAR",
                 help="Set delimiter character")
parser.add_option("-n", "--numeric", action="store_true", default=False,
                 help="Attempt to sort numerically instead of using strings.")
parser.add_option("--quote-all",
                  dest="quoting", action="store_const", const=csv.QUOTE_ALL,
                  help="Quote all fields.")
parser.add_option("--quote-minimal",
                  dest="quoting", action="store_const", const=csv.QUOTE_MINIMAL,
                  default=csv.QUOTE_MINIMAL,
                  help="Quote only when necessary.")
parser.add_option("--quote-nonnumeric",
                  dest="quoting", action="store_const", const=csv.QUOTE_NONNUMERIC,
                  help="Quote only non-numeric fields.")
parser.add_option("--trim-spaces", action="store_true", default=False,
                  help="Trim spaces leading/trailing spaces in all cells.  "
                  "(This excludes the header row.)")
parser.add_option("-c", "--pad-columns", action="store", type="int", default=0,
                  metavar="NUM", help="Pad empty cells so that NUM columns "
                  "always exist in the output.  (Default:  no changes).")

def files_differ(f1, f2, cmp_size=16*1024):
    if os.stat(f1).st_size != os.stat(f2).st_size:
        return True
    fp1 = open(f1, "rb")
    fp2 = open(f2, "rb")
    c1 = c2 = " "
    while c1 or c2:
        if c1 != c2:
            return True
        c1 = fp1.read(cmp_size)
        c2 = fp2.read(cmp_size)
    return False


def sort_csv_file(src, dst, delimiter, quoting, trim_spaces=False, pad_columns=0, sort_numeric=False):
    reader = iter(csv.reader(open(src), delimiter=delimiter))
    header = reader.next()
    columns = len(header)
    rows = []
    for i,row in enumerate(reader):
        if trim_spaces:
            row = [ v.trim() for v in row ]
        if sort_numeric:
            newrow = []
            for v in row:
                try:
                    v = Decimal(v)
                except InvalidOperation:
                    # Not numeric
                    pass
                newrow.append(v)
            row = newrow
            del newrow
        row_len = len(row)
        if pad_columns:
            if row_len < pad_columns:
                # Add missing cells
                # DEBUG:  print "Add missing cells:   %d  %r" % (pad_columns-row_len, row)
                row += ["",] * (pad_columns-row_len)
            else:
                while row_len > pad_columns:
                    # Trim off any extra empty trailing columns
                    if row[-1] == "":
                        del row[-1]
                    else:
                        break
                    row_len = len(row)
        elif row_len != columns:
            print "Found incorrect number of rows on line %d:  row=%r" % (i+2, row)
        rows.append(row)
    rows.sort()

    writer = csv.writer(open(dst,"w"), delimiter=delimiter, quoting=quoting)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)


if __name__ == '__main__':
    (options, args) = parser.parse_args()
    for fn in args:
        # print "Sorting file:  %s" % (fn,)
        if options.in_place:
            temp_file = fn + ".sort_tmp"
            backup = fn + ".bak"
            sort_csv_file(fn, temp_file, options.delimiter, options.quoting,
                          options.trim_spaces, options.pad_columns,
                          options.numeric)
            if files_differ(fn, temp_file):
                print "Updating file:  %s" % (fn,)
            else:
                print "No changes to file:  %s" % (fn,)
                os.unlink(temp_file)
                continue
            if os.path.isfile(backup):
                # Remove old backup
                os.unlink(backup)
            os.rename(fn, backup)
            os.rename(temp_file, fn)
        else:
            new_file = fn + ".new"
            sort_csv_file(fn, new_file, options.delimiter, options.quoting,
                          options.trim_spaces, options.pad_columns,
                          options.numeric)
            if files_differ(fn, new_file):
                print "Sorted file saved as:  %s" % (new_file)
            else:
                print "No changes made."
                os.unlink(new_file)
