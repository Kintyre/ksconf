"""

Incomplete documentation available here:

https://docs.splunk.com/Documentation/Splunk/latest/Admin/Defaultmetaconf

Specifically, attribute-level ACls aren't discussed nor is the magic "import" directive.


LEVELS:

    0 - global  (or 1 stanza="default")
    1 - conf
    2 - stanzas
    3 - attribute
"""

from __future__ import absolute_import, unicode_literals

import re
from urllib.parse import quote, unquote

from ksconf.conf.parser import GLOBAL_STANZA, parse_conf

"""

Another way to split out the hierarchy.   (Issues:   No way to warn if too many "/"s.)

d = dict(zip(("conf", "stanza", "attribute"), (unquote(p) for p in stanza_name.split("/"))))


    {"conf" :

"""


class MetaLayer:
    def __init__(self, name):
        self.name = name
        self._data = {}             # Current level data
        self._children = {}         # Named children, levels

    def resolve(self, name):
        try:
            return self._children[name]
        except KeyError:
            baby = MetaLayer(name)
            self._children[name] = baby
            return baby

    def update(self, *args, **kwargs):
        self._data.update(*args, **kwargs)

    @property
    def data(self):
        return self._data

    def walk(self, _prefix=()):
        if self._data:
            yield _prefix
        if self._children:
            for child_name, child in self._children.items():
                yield from child.walk(_prefix=_prefix + (child_name,))

    def items(self, prefix=None):
        """ Helpful when rebuilding the input file. """
        if prefix is None:
            prefix = ()
        if self._data:
            yield prefix, self._data
        if self._children:
            for child_name, child in self._children.items():
                yield from child.items(prefix=prefix + (child_name,))


class MetaData:

    regex_access = r"(?:^|\s*,\s*)(?P<action>read|write)\s*:\s*\[\s*(?P<roles>[^\]]+?)\s*\]"

    def __init__(self):
        self._meta = MetaLayer("")

    @staticmethod
    def expand_layers(layers):
        """
        :param layers: layer of stanzas, starting with the global ending with conf/stanza/attr
        :type layers: list(dict)
        :return:  Expanded layer
        :rtype: dict
        """
        # type: (list(layers)) -> dict
        exp = {}
        for layer in layers:
            if layer:
                exp.update(layer)
        return exp

    @classmethod
    def parse_meta(cls, stanza):
        """
        Split out the values of 'access' (maybe more someday)
        :param stanza: content of a meta stanza
        :return: extended meta data
        :rtype: dict
        """
        # Do we really need to do this?  .. seems safer for now
        stanza = stanza.copy()
        if "access" in stanza:
            access = stanza["access"]
            for match in re.finditer(cls.regex_access, access):
                stanza_name = "access.{}".format(match.group("action"))
                values = [role.strip() for role in match.group("roles").split(",")]
                stanza[stanza_name] = values
        return stanza

    def get_layer(self, *names):
        node = self._meta
        for name in names:
            node = node.resolve(name)
        return node

    def get(self, *names):
        node = self._meta
        layers = [node.data]
        for name in names:
            node = node.resolve(name)
            layers.append(node.data)
        d = self.expand_layers(layers)
        # Parser access:   split out 'read' vs 'write', return as list
        # d["acesss"]
        return self.parse_meta(d)

    def feed_file(self, stream):
        conf = parse_conf(stream)
        self.feed_conf(conf)

    def feed_conf(self, conf):
        for stanza_name, stanza_data in conf.items():
            if stanza_name is GLOBAL_STANZA:
                parts = []
            else:
                parts = [unquote(p) for p in stanza_name.split("/")]
                if len(parts) == 1 and parts[0] in (GLOBAL_STANZA, "", "default", "global"):
                    parts = []
            meta_layer = self.get_layer(*parts)
            meta_layer.update(stanza_data)

    def iter_raw(self):
        """ RAW """
        return self._meta.items()

    def walk(self):
        for path in self._meta.walk():
            yield (path, self.get(*path))

    def write_stream(self, stream, sort=True):
        if sort:
            # Prefix level # to list for sorting purposes
            data = [(len(parts), parts, payload) for parts, payload in self.iter_raw()]
            data.sort()
            raw = [(i[1], i[2]) for i in data]
            del data
        else:
            raw = self.iter_raw()

        for parts, payload in raw:
            stanza = "/".join(quote(p, "") for p in parts)
            stream.write("[{}]\n".format(stanza))
            for attr in sorted(payload):
                value = payload[attr]
                if attr.startswith("#"):
                    stream.write("{0}\n".format(value))
                else:
                    stream.write("{} = {}\n".format(attr, value))
            # Trailing EOL, oh well...  fix that later
            stream.write("\n")
