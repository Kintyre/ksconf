import json
import os
import re
from io import BytesIO
from typing import TYPE_CHECKING, Any, List

from ksconf.util.file import ReluctantWriter

etree = None


if TYPE_CHECKING:
    from lxml.etree import ElementTree
else:
    ElementTree = Any


def _import_etree():
    # Lazy loaded etree; This prevents crashing at module import if not installed
    g = globals()
    from lxml import etree
    g["etree"] = etree


class FileReadlinesCache:
    """ Silly workaround for CDATA detection... """

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


class SplunkSimpleXmlFormatter:
    keep_tags = {"latest", "earliest", "set", "label", "fieldset", "default", "search", "option"}

    def __init__(self):
        if etree is None:
            _import_etree()

    @classmethod
    def indent_tree(cls, elem: ElementTree, level=0, indent=2):
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
    def expand_tags(cls, elem: ElementTree, tags: set):
        """Keep <elem></elem> instead of shortening to <elem/>"""
        if elem.tag in tags and elem.text is None:
            # By setting this to an empty string (vs None), the trailing tag is kept
            elem.text = ""
        for c in elem:
            cls.expand_tags(c, tags)

    @staticmethod
    def cdata_tags(elem: ElementTree, tags: List[str]):
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
                    # print(f"Found source line:  {line}")
                    return True
            return False

        for tag in tags:
            for e in elem.findall(f".//{tag}"):
                if e.text and e.text.strip():
                    # Determine if the data is ALREADY in a CDATA element
                    # if isinstance(e.text, etree.CDATA):   # Doesn't work...
                    if already_using_cdata(e):
                        pass
                    elif re.search(r'[<>&]', e.text):
                        # print(f"SHOULD BE CDATA:   {e.text}")
                        # Convert text to CDATA
                        e.text = etree.CDATA(e.text)

    @staticmethod
    def guess_indent(elem: ElementTree, default=2):
        if elem.text:
            prefix = elem.text.strip("\r\n")
            indent = len(prefix) or default
            # print(f"Found indent={indent}")
        else:
            indent = default
        return indent

    @classmethod
    def format_json(cls, elem: ElementTree, indent=2):
        """  Format JSON data within a Dashboard Studio dashboard.   This is
        still pretty limited (for example, long searches still show up on a
        single line), but this give you at least a fighting change to figure
        out what's different.
        """

        # Abort if this isn't Dashboard Studio embedded in Simple XML
        if not elem.attrib.get("version") == "2":
            return

        tags = ["definition", "assets"]
        for tag in tags:
            for e in elem.findall(f".//{tag}"):
                if e.text:
                    data = json.loads(e.text)
                    output = json.dumps(data, indent=indent, sort_keys=False)
                    # Multiple lines?  Spread out CDATA header/trailer
                    if "\n" in output:
                        output = f"\n{output}\n"
                    e.text = etree.CDATA(output)

    @classmethod
    def format_xml(cls, src, dest, default_indent=2):
        # Copied from https://stackoverflow.com/a/5649263/315892
        parser = etree.XMLParser(resolve_entities=False, strip_cdata=False)
        document = etree.parse(src, parser)
        root = document.getroot()
        i = cls.guess_indent(root, default_indent)
        cls.indent_tree(root, indent=i)
        cls.cdata_tags(root, ["query"])
        cls.format_json(root, indent=i)
        cls.expand_tags(root, cls.keep_tags)

        b = BytesIO()
        document.write(b, pretty_print=True, encoding='utf-8')
        writer = ReluctantWriter(dest, "wb")
        with writer as f:
            f.write(b.getvalue().strip(b"\r\n"))
            f.write(b"\n")
        return writer.change_needed
