"""

LEVELS:

    0 - global  (or 1 stanza="default")
    1 - conf
    2 - stanzas
    3 - attribute
"""


"""

Another way to split out the hierarchy.   (Issues:   No way to warn if too many "/"s.)

d = dict(zip(("conf", "stanza", "attribute"), (unquote(p) for p in stanza_name.split("/"))))


    {"conf" :

"""

import re

from urllib import unquote

from ksconf.conf.parser import parse_conf
from ksconf.conf.merge import merge_conf_dicts



class MetaLayer(object):
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




class MetaData(object):

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
        # type: list(layers) -> dict
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
                values = [ role.strip() for role in match.group("roles").split(",") ]
                stanza[stanza_name] = values
        return stanza

    def get_layer(self, *names):
        node = self._meta
        for name in names:
            node = node.resolve(name)
        return node

    def get_combined(self, *names):
        node = self._meta
        layers = [ node.data ]
        for name in names:
            node = node.resolve(name)
            layers.append(node.data)
        d = self.expand_layers(layers)
        # Parser access:   split out 'read' vs 'write', return as list
        #d["acesss"]
        return self.parse_meta(d)

    def feed(self, stream):
        conf = parse_conf(stream)
        for stanza_name, stanza_data in conf.items():
            parts = [ unquote(p) for p in stanza_name.split("/") ]
            if len(parts) == 1 and parts[0] in ("", "default", "global"):
                parts = []
            meta_layer = self.get_layer(*parts)
            meta_layer.update(stanza_data)

#    def iter_all(self):
#        for
