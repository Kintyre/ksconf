#!/usr/bin/env python

from lxml import etree
import re


def indent_tree(elem, level=0, indent=2):
    # Copied from http://effbot.org/zone/element-lib.htm#prettyprint
    itxt = " " * indent
    i = "\n" + level * itxt
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + itxt
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_tree(elem, level+1, indent)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    # XXX:  How do we remove the trailing "\n" on the very last node?

keep_tags = { "latest", "earliest", "set", "label", "fieldset", "default", "search", "option" }

def expand_tags(elem, tags):
    """Keep <elem></elem> instead of shortening to <elem/>"""
    # type:  (etree.ElementTree, set)
    if elem.tag in tags and elem.text is None:
        # By setting this to an empty string (vs None), the trailing tag is kept
        elem.text = ""
    for c in elem:
        expand_tags(c, tags)


def cdata_tags(elem, tags):
    """ Expand text to CDATA, if it isn't already. """
    _cache = {}
    def already_using_cdata(elem):
        # Super wonky hack, but I can't find any progamatic way to determine if .text (or some part of it) contains CDATA. There seems to be some hidden magic here, in how this is implemented.
        # TODO:  We should at least CACHE the contents of the file....
        CDATA = "<![CDATA["
        if elem.base not in _cache:
            _cache[elem.base] = open(elem.base).readlines()
        lines = _cache[elem.base]
        lineno = elem.sourceline-1
        source_lines = lines[lineno:lineno+2]
        for line in source_lines:
            if CDATA in line:
                print("Found sourceline:  {}".format(line))
                return True
        return False

    for tag in tags:
        for e in elem.findall(".//{}".format(tag)):
            if e.text and e.text.strip():
                # How do we determine if the data is ALREADY in a CDATA element?!??!
                #if isinstance(e.text, etree.CDATA):
                if already_using_cdata(e):
                    pass
                elif re.search(r'[<>&]', e.text):
                    # Convert text to CDATA
                    e.text = etree.CDATA(e.text)
                else:
                    pass


def guess_indent(elem):
    prefix = elem.text.strip("\r\n")
    indent = len(prefix) or 2
    print("Found indent={}".format(indent))
    return indent


def pretty_print_xml(path):
    # Copied from https://stackoverflow.com/a/5649263/315892
    parser = etree.XMLParser(resolve_entities=False, strip_cdata=False)
    document = etree.parse(path, parser)
    root = document.getroot()
    i = guess_indent(root)
    indent_tree(root, indent=i)
    cdata_tags(root, ["query"])
    expand_tags(root, keep_tags)
    from io import BytesIO
    b = BytesIO()
    document.write(b, pretty_print=True, encoding='utf-8')

    # Wonky workaround to avoid uncessary newlines at the end of the file
    with open(path, "wb") as f:
        f.write(b.getvalue().strip("\r\n"))
        # Single newline
        f.write("\n")
    #document.write(path, encoding='utf-8')


if __name__ == '__main__':
    import sys
    for fn in sys.argv[1:]:
        print("formatting {}".format(fn))
        pretty_print_xml(fn)
