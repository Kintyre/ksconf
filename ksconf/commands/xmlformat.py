""" SUBCOMMAND:  ksconf xml-format <XML>

Usage example:   (Nice pre-commit script)

    find default/data/ui -name '*.xml' | ksconf xml-format -

"""
from __future__ import absolute_import, unicode_literals

import re
import os
from io import BytesIO, StringIO
from collections import Counter

from six import PY2

from ksconf.commands import KsconfCmd, dedent
from ksconf.consts import EXIT_CODE_SUCCESS, EXIT_CODE_FORMAT_APPLIED, EXIT_CODE_BAD_CONF_FILE,\
    EXIT_CODE_INTERNAL_ERROR
from ksconf.util import debug_traceback
from ksconf.util.completers import conf_files_completer
from ksconf.util.file import _stdin_iter, ReluctantWriter

# Lazy loaded by _handle_imports()
etree = None



class FileReadlinesCache(object):
    """ Silly class as a hacky workaround for CDATA detection... """
    def __init__(self):
        self.cache = {}

    @staticmethod
    def convert_filename(filename):
        if filename.startswith("file:"):
            filename = filename[5:]
            if filename[0] == "/" and filename[2] == ":":
                # Example:   file:/c:/temp/.....
                filename = filename[1:]
            filename = os.path.normpath(filename)
        return filename

    def readlines(self, filename):
        if filename not in self.cache:
            self.cache[filename] = self._readlines(filename)
        return self.cache[filename]

    def _readlines(self, filename):
        filename = self.convert_filename(filename)
        with open(filename) as stream:
            return stream.readlines()



class XmlFormatCmd(KsconfCmd):
    help = "Normalize XML view and nav files"
    description = dedent("""
    Normalize and apply consistent XML indentation and CDATA usage for XML dashboards and
    navigation files.

    Technically this could be used on *any* XML file, but certain element names specific to Splunk's
    simple XML dashboards are handled specially, and therefore could result in unusable results.

    The expected indentation level is guessed based on the first element indentation, but can be
    explicitly set if not detectable.
    """)
    maturity = "alpha"

    keep_tags = {"latest", "earliest", "set", "label", "fieldset", "default", "search", "option"}

    @classmethod
    def _handle_imports(cls):
        g = globals()
        if globals()["etree"]:
            return
        from lxml import etree
        cls.version_extra = "lxml {}".format(etree.__version__)
        g["etree"] = etree

    @classmethod
    def indent_tree(cls, elem, level=0, indent=2):
        # Copied from http://effbot.org/zone/element-lib.htm#prettyprint
        itxt = " " * indent
        i = "\n" + level * itxt
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + itxt
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                cls.indent_tree(elem, level + 1, indent)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    @classmethod
    def expand_tags(cls, elem, tags):
        """Keep <elem></elem> instead of shortening to <elem/>"""
        # type:  (etree.ElementTree, set)
        if elem.tag in tags and elem.text is None:
            # By setting this to an empty string (vs None), the trailing tag is kept
            elem.text = ""
        for c in elem:
            cls.expand_tags(c, tags)

    @staticmethod
    def cdata_tags(elem, tags):
        """ Expand text to CDATA, if it isn't already. """
        cache = FileReadlinesCache()
        CDATA = "<![CDATA["

        def already_using_cdata(elem):
            # WARNING:  Super wonky hack!  I can't find any programmatic way to determine if .text
            # (or some part of it) contains CDATA.  There seems to be some hidden magic here,
            # in how this is implemented.  Patches welcome!

            # HACK optimization:   Cache the contents of the file to prevent dozens of re-reads
            lines = cache.readlines(elem.base)

            lineno = elem.sourceline - 1
            source_lines = lines[lineno:lineno + 2]
            for line in source_lines:
                if CDATA in line:
                    #print("Found source line:  {}".format(line))
                    return True
            return False

        for tag in tags:
            for e in elem.findall(".//{}".format(tag)):
                if e.text and e.text.strip():
                    # Determine if the data is ALREADY in a CDATA element
                    # if isinstance(e.text, etree.CDATA):   # Doesn't work...
                    if already_using_cdata(e):
                        pass
                    elif re.search(r'[<>&]', e.text):
                        #print("SHOULD BE CDATA:   {}".format(e.text))
                        # Convert text to CDATA
                        e.text = etree.CDATA(e.text)

    @staticmethod
    def guess_indent(elem, default=2):
        if elem.text:
            prefix = elem.text.strip("\r\n")
            indent = len(prefix) or default
            # print("Found indent={}".format(indent))
        else:
            indent = default
        return indent

    @classmethod
    def pretty_print_xml(cls, path, default_indent=2):
        # Copied from https://stackoverflow.com/a/5649263/315892
        parser = etree.XMLParser(resolve_entities=False, strip_cdata=False)
        document = etree.parse(path, parser)
        root = document.getroot()
        i = cls.guess_indent(root, default_indent)
        cls.indent_tree(root, indent=i)
        cls.cdata_tags(root, ["query"])
        cls.expand_tags(root, cls.keep_tags)


        b = BytesIO()
        document.write(b, pretty_print=True, encoding='utf-8')
        writer = ReluctantWriter(path, "wb")
        with writer as f:
            if PY2:
                f.write(b.getvalue().strip("\r\n"))
                # Single newline
                f.write("\n")
            else:
                f.write(b.getvalue().strip(b"\r\n"))
                f.write(b"\n")
        return writer.change_needed


    def register_args(self, parser):
        parser.add_argument("xml", metavar="FILE", nargs="+", help=dedent("""\
            One or more XML files to check.
            If '-' is given, then a list of files is read from standard input""")
                         ).completer = conf_files_completer
        parser.add_argument("--indent", type=int, default=2, help=
            "Number of spaces.  This is only used if indentation cannot be "
            "guessed from the existing file.")
        parser.add_argument("--quiet", "-q", default=False, action="store_true",
                            help="Reduce the volume of output.")

    def run(self, args):
        # Should we read a list of conf files from STDIN?
        if len(args.xml) == 1 and args.xml[0] == "-":
            files = _stdin_iter()
        else:
            files = args.xml
        c = Counter()
        exit_code = EXIT_CODE_SUCCESS
        for fn in files:
            c["checked"] += 1
            if not os.path.isfile(fn):
                self.stderr.write("Skipping missing file:  {0}\n".format(fn))
                c["missing"] += 1
                continue
            try:
                if self.pretty_print_xml(fn, args.indent):
                    self.stderr.write("Replaced file {0} with formatted content\n".format(fn))
                    c["changed"] += 1
                else:
                    if not args.quiet:
                        self.stderr.write("Already formatted {0}\n".format(fn))
                    c["no-action"] += 1
                self.stderr.flush()
            except etree.ParseError as e:
                self.stderr.write("Error parsing file {0}:  {1}\n".format(fn, e))
                self.stderr.flush()
                c["error"] += 1
                exit_code = EXIT_CODE_BAD_CONF_FILE
            except Exception as e:  # pragma: no cover
                self.stderr.write("Unhandled top-level exception while parsing {0}.  "
                                  "Aborting.\n{1}\n".format(fn, e))
                debug_traceback()
                c["error"] += 1
                exit_code = EXIT_CODE_INTERNAL_ERROR
                break

        if not exit_code and c["changed"] > 0:
            exit_code = EXIT_CODE_FORMAT_APPLIED

        if True:  # show stats or verbose
            self.stdout.write("Completed formatting {0[checked]} files.  rc={1} Breakdown:\n"
                              "   {0[changed]} files were formatted successfully.\n"
                              "   {0[no-action]} files were already formatted.\n"
                              "   {0[error]} files failed.\n".format(c, exit_code))
        return exit_code
