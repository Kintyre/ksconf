from __future__ import absolute_import, unicode_literals

import sys
import os
import re
import ksconf.ext.six as six


from ksconf.util.file import relwalk
from collections import defaultdict


"""

LayerRootBase has one or more 'Layer', each layer has one or more 'File's.


LayerRoot methods:

    - list_files():   Return superset of all file names returned by all layers (order undefined)
    - walk():         Return list_files() like content in a os.walk() (or relwalker) like way -- must consider directory order, useful for copying tree, for example.
                      Assumption for now:  Don't return layer per file, just what files exist.  Ask about layers per file later.
    - list_layers():  Iterate over layer objects (metadata retrievable, on demand)
    - get_file():     Return files (in ranked layer order)


Other possible methods:
    list_dirs():      Return list of known directories?   Not sure how we want this part to work.  Perhaps walk() is good enough?


dotD style layers:

    LayerRootDotD has one or more 'LayerMount', each LayerMount has one or more Layer, which has one or more 'File's.



Remember:  This must work for NON-layered directories too, hopefully with minimal overhead.

This must work with an explicitly given list of layers

"""




def _path_join(*parts):
    """ A slightly smarter / more flexible path appender.
    Drop any None or "." elements
    """
    parts = [p for p in parts if p is not None]
    return os.path.join(*parts)


# Exceptions

class LayerException(Exception):
    pass


class LayerUsageException(LayerException):
    pass







class LayerRootBase(object):
    """ All 'path's here are relative to the ROOT. """

    class File(object):
        __slots__ = ["layer", "relative_path", "size", "mtime", "_cache"]

        def __init__(self, layer, relative_path, size=None, mtime=None):
            self.layer = layer
            self.relative_path = relative_path
            self.size = size
            self.mtime = mtime

        @property
        def physical_path(self):
            return _path_join(self.layer.root, self.layer.physical_path, self.relative_path)

        @property
        def logical_path(self):
            return _path_join(self.layer.logical_path, self.relative_path)

    class Layer(object):
        """ Basic layer Container:   Connects logical and physical paths. """
        __slots__ = ["name", "root", "logical_path", "physical_path", "_file_cls"]

        def __init__(self, name, root, physical, logical, file_cls):
            self.name = name
            self.root = root
            self.physical_path = physical
            self.logical_path = logical
            self._file_cls = file_cls

        def walk(self):
            # In the simple case, this is good enough.   Some subclasses will need to override
            for (root, dirs, files) in relwalk(_path_join(self.root, self.physical_path)):
                yield (root, dirs, files)

        def list_files(self):
            File = self._file_cls
            for (root, dirs, files) in self.walk():
                for file in files:
                    yield File(self, _path_join(root, file))

        def get_file(self, rel_path):
            """ Return file object, if it exists. """
            File = self._file_cls
            path_p = _path_join(self.physical_path, rel_path)
            if os.path.isfile(path_p):
                return File(self, rel_path)


    def __init__(self):
        self._layers = []

    def order_layers(self):
        raise NotImplementedError

    def add_layer(self, layer, do_sort=True):
        self._layers.append(layer)
        if do_sort:
            self.order_layers()

    def list_layers(self):
        return self._layers

    def list_files(self):
        """ Return a list of logical paths. """
        files = set()
        for layer in self._layers:
            for file_ in layer.list_files():
                files.add(file_.logical_path)
        return list(files)

    def get_path(self, path):
        """ return all layers associated with file path. """
        for layer in self._layers:
            file_ = layer.get_file(path)
            if file_:
                yield file_

    def get_path_layers(self, path):
        pass


class DirectLayerRoot(LayerRootBase):
    """
    A very simple direct LayerRoot implementation that relies on all layer paths to be explicitly
    given without any automatic detection mechanisms.  You can think of this as the legacy
    implementation.
    """
    def add_layer(self, path):
        Layer, File = self.Layer, self.File
        # Layer name should be considered arbitrary and unimportant here
        layer_name = os.path.basename(path)
        if not os.path.isdir(path):
            raise LayerUsageException("Layers must be directories.  "
                                      "Given path '{}' is not a directory.".format(path))
        layer = Layer(layer_name, path, None, None, file_cls=File)
        super(DirectLayerRoot, self).add_layer(layer)

    def order_layers(self):
        # No op.  Irrelevant as layers are given (CLI) in the order they should be applied.
        pass


"""


    Layers must be discovered depth-first,
    Files must be walked breath-first?  Is that right?

    MyApp/                          <- Root + MountPointTransparent (contains 1 layer)
        bin/
        default.d/                  <- MountPoint Disconnect from parent layer
            10-upstream             <- Layer
            20-kintyre-core         <- Layer
            99-override             <- Layer
        static/
        lookup.d/



Q:  What about nested layers, should that be supported?  (Yes, this is an horrific example)
A:  Let's support if it just works naturally, otherwise, let's not go to extra lengths to support
A:  Multiple LayerRoots SHOULD be supported.

    MyApp/                          <- LayerRoot & Layer (Anonymous -- lowest ranking)
        lib.d/
            10-upstream
                botocore/
                requests/
            20-kintyre              <-- LayerMount
                botocore.d/
                    10-python3      <-- Layer (nested)
                    20-python2      <-- Layer (nested)
                requests/
        default.d/                  <- Disconnect from parent layer
            10-upstream             <- Layer
            20-kintyre-core         <- Layer
            99-override             <- Layer
        static/

"""




###  Q:  How do we mark "mount-points" in the directory structure to keep multiple layers from claiming the same files?????
class DotDLayerRoot(LayerRootBase):

    class Layer(LayerRootBase.Layer):
        __slots__ = ["prune_points"]

        def __init__(self, name, root, physical, logical, file_cls, prune_points=None):
            super(DotDLayerRoot.Layer, self).__init__(name, root, physical, logical, file_cls)
            self.prune_points = set(prune_points) if prune_points else set()

        def walk(self):
            for (root, dirs, files) in super(DotDLayerRoot.Layer, self).walk():
                if root in self.prune_points:
                    # Cleanup files/dirs to keep walk() from descending deeper
                    del dirs[:]
                else:
                    yield (root, dirs, files)

    '''
    class MountBase(object):
        def __init__(self, path):
            self.path = path

    class MountTransparent(MountBase):
        """ Pass through files as-is, no manipulation. """
        pass

    class MountDotD(MountBase):
        def __init__(self, path):
            super(DotDLayerRoot.MountDotD, self).__init__(path)
    '''

    mount_regex = re.compile("(?P<realname>[\w_.-]+)\.d$")
    layer_regex = re.compile("(?P<layer>\d\d-[\w_.-]+)")

    def __init__(self):
        super(DotDLayerRoot, self).__init__()
        #self.root = None
        self._root_layer = None
        self._mount_points = defaultdict(list)

    def set_root(self, root):
        """ Set a root path, and auto discover all '.d' directories.

        Note:  We currently only support '.d/<layer>' directories, so something like
        `default.d/10-props.conf` won't be handled here.
        """
        Layer, File = self.Layer, self.File
        for (top, dirs, files) in relwalk(root, topdown=False):
            del files
            mount_mo = self.mount_regex.match(top)
            if mount_mo:
                for dir_ in dirs:
                    dir_mo = self.layer_regex.match(dir_)
                    if dir_mo:
                        # XXX: Nested layers breakage, must substitute multiple ".d" folders in `top`
                        layer = Layer(dir_mo.group("layer"),
                                      root,
                                      os.path.join(root, top, dir_),
                                      os.path.join(os.path.dirname(top), mount_mo.group("realname")),
                                      file_cls=File)
                        self.add_layer(layer)
                        self._mount_points[top].append(dir_)
                    else:
                        # XXX: Give the use the option of logging the near-matches (could indicate a
                        # problem in the config, or could be some other legit directory structure)
                        pass

        # XXX: Adding <root> should be skipped if (and only if) root itself if a '.d' folder
        # Very last operation, add the top directory as the final layer (lowest rank)
        prune_points = [os.path.join(mount, layer) for mount, layers in self._mount_points.items()
                        for layer in layers]
        layer = Layer("<root>", root, None, None, file_cls=File, prune_points=prune_points)
        self.add_layer(layer, do_sort=False)
        self._root_layer = layer

    def list_layers(self):
        # Return all but the root layer.
        # Avoiding self._layers[:-1] because there could be cases where root isn't included.
        return [l for l in self._layers if l is not self._root_layer]

    def order_layers(self):
        # Sort based on layer name (or other sorting priority:  00-<name> to 99-<name>
        self._layers.sort(key=lambda l: l.name)







def run_oldshool(args):

    combined19 = DirectLayerRoot()
    # Take CLI args and apply to root
    for src in args.source:
        combined19.add_layer(src)

    layers = list(combined19.list_layers())
    print("Given layers:  {}".format(layers))

    files = combined19.list_files()
    print("Files:  {}", files)
