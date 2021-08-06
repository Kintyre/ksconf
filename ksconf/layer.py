from __future__ import absolute_import, unicode_literals

import os
import re
from collections import defaultdict
from fnmatch import fnmatch

from ksconf.util.file import relwalk

"""

LayerRootBase has one or more 'Layer', each layer has one or more 'File's.


LayerRoot methods:

    - list_files():   Return superset of all file names returned by all layers (order undefined)
    - walk():         Return list_files() like content in a os.walk() (or relwalker) like way --
                      must consider directory order, useful for copying tree, for example.
                      Assumption for now:  Don't return layer per file, just what files exist.
                      Ask about layers per file later.
    - list_layers():  Iterate over layer objects (metadata retrievable, on demand)
    - get_file():     Return files (in ranked layer order)


Other possible methods:
    list_dirs():      Return list of known directories?   Not sure how we want this part to work.
                      Perhaps walk() is good enough?


dotD style layers:

    LayerRootDotD   has one or more 'LayerMount', each LayerMount has one or more Layer,
                    which has one or more 'File's.



Remember:  This must work for NON-layered directories too, hopefully with minimal overhead.

This must work with an explicitly given list of layers

"""


def _path_join(*parts):
    """ A slightly smarter / more flexible path appender.
    Drop any None or "." elements
    """
    parts = [p for p in parts if p is not None]
    return os.path.join(*parts)


def path_in_layer(layer, path, sep=os.path.sep):
    """ Check to see if path exist within layer.
    Returns either None, or the path without the shared prefix with layer.
    """
    # Using 'sep' over os.path.join / os.path.split should be okay here as we should only ever be
    # given relative paths (no Windows UNC/drive letters)
    if layer is None:
        # Return as-is, since layer is root
        return path
    layer_parts = layer.split(sep)
    layer_count = len(layer_parts)
    path_parts = path.split(sep)
    if len(path_parts) < layer_count:
        return False
    path_suffix = path_parts[:layer_count]
    if layer_parts != path_suffix:
        return False
    return sep.join(path_parts[layer_count:])


# Exceptions

class LayerException(Exception):
    pass


class LayerUsageException(LayerException):
    pass


class LayerFilter(object):
    _valid_actions = ("include", "exclude")

    def __init__(self):
        self._rules = []

    def add_rule(self, action, pattern):
        # If no filter rules have been setup yet, be sure to set the default
        if action not in self._valid_actions:
            raise ValueError("Unknown action of {}.  Valid actions include: {}"
                             .format(action, self._valid_actions))
        if not self._rules:
            if action == "include":
                first_filter = ("exclude", "*")
            elif "exclude":
                first_filter = ("include", "*")
            self._rules.append(first_filter)
        self._rules.append((action, pattern))

    def evaluate(self, layer):
        # type: (LayerRootBase.Layer) -> bool
        response = True
        layer_name = layer.name
        for rule_action, rule_pattern in self._rules:
            if fnmatch(layer_name, rule_pattern):
                response = rule_action == "include"
        return response

    __call__ = evaluate


class LayerConfig(object):

    def __init__(self):
        # Set defaults
        self.follow_symlink = False
        self.block_files = re.compile(r"\.(bak|swp)$")
        self.block_dirs = {".git"}


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
        __slots__ = ["name", "root", "logical_path", "physical_path", "config", "_file_cls"]

        def __init__(self, name, root, physical, logical, config, file_cls):
            # type: (str, str, str, str, LayerConfig, type) -> None
            self.name = name
            self.root = root
            self.physical_path = physical
            self.logical_path = logical
            self.config = config
            self._file_cls = file_cls

        def walk(self):
            # In the simple case, this is good enough.   Some subclasses will need to override
            for (root, dirs, files) in relwalk(_path_join(self.root, self.physical_path),
                                               followlinks=self.config.follow_symlink):
                files = [f for f in files if not self.config.block_files.search(f)]
                for d in list(dirs):
                    if d in self.config.block_dirs:
                        dirs.remove(d)
                yield (root, dirs, files)

        def list_files(self):
            File = self._file_cls
            for (top, dirs, files) in self.walk():
                for file in files:
                    yield File(self, _path_join(top, file))

        def get_file(self, path):
            """ Return file object (by logical path), if it exists in this layer. """
            # XXX: There's probably ways to optimize this.  fine for now (correctness over speed)
            File = self._file_cls
            rel_path = path_in_layer(self.logical_path, path)
            if not rel_path:
                return None
            file_ = File(self, rel_path)
            if os.path.isfile(file_.physical_path):
                return file_
            '''
            path_p = _path_join(self.root, self.physical_path, rel_path)
            if os.path.isfile(path_p):
                return File(self, rel_path)
            '''

    def __init__(self, config=None):
        self._layers = []
        self.layer_filter = None
        self.config = config or LayerConfig()

    def apply_filter(self, layer_filter):
        """
        Apply a destructive filter to all layers.  layer_filter(layer) will be called one for each
        layer, if the filter returns True than the layer is kept.  Root layers are always kept.
        """
        layers = [l for l in self._layers if layer_filter(l)]
        result = self._layers != layers
        self._layers = layers
        return result

    def order_layers(self):
        raise NotImplementedError

    def add_layer(self, layer, do_sort=True):
        self._layers.append(layer)
        if do_sort:
            self.order_layers()

    def list_layers(self):
        return self._layers

    def list_layer_names(self):
        return [l.name for l in self.list_layers()]

    def list_files(self):
        """ Return a list of logical paths. """
        files = set()
        for layer in self._layers:
            for file_ in layer.list_files():
                files.add(file_.logical_path)
        return list(files)

    def get_file(self, path):
        """ return all layers associated with the given relative path. """
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
        layer = Layer(layer_name, path, None, None, config=self.config, file_cls=File)
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


# Q:  How do we mark "mount-points" in the directory structure to keep multiple layers
#     from claiming the same files?????
class DotDLayerRoot(LayerRootBase):

    class Layer(LayerRootBase.Layer):
        __slots__ = ["prune_points"]

        def __init__(self, name, root, physical, logical, config, file_cls, prune_points=None):
            super(DotDLayerRoot.Layer, self).__init__(name, root, physical, logical, config=config,
                                                      file_cls=file_cls)
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

    mount_regex = re.compile(r"(?P<realname>[\w_.-]+)\.d$")
    layer_regex = re.compile(r"(?P<layer>\d\d-[\w_.-]+)")

    def __init__(self, config=None):
        super(DotDLayerRoot, self).__init__(config)
        # self.root = None
        self._root_layer = None
        self._mount_points = defaultdict(list)

    def apply_filter(self, layer_filter):
        # Apply filter function, but also be sure to keep the root layer
        def fltr(l):
            return l is self._root_layer or layer_filter(l)
        return super(DotDLayerRoot, self).apply_filter(fltr)

    def set_root(self, root, follow_symlinks=None):
        """ Set a root path, and auto discover all '.d' directories.

        Note:  We currently only support '.d/<layer>' directories, a file like
        `default.d/10-props.conf` won't be handled here.
        """
        Layer, File = self.Layer, self.File
        if follow_symlinks is None:
            follow_symlinks = self.config.follow_symlink

        for (top, dirs, files) in relwalk(root, topdown=False, followlinks=follow_symlinks):
            del files

            top_dirname, top_basename = os.path.split(top)
            mount_mo = self.mount_regex.match(top_basename)

            if mount_mo:
                for dir_ in dirs:
                    dir_mo = self.layer_regex.match(dir_)
                    if dir_mo:
                        # XXX: Nested layers breakage, must substitute multiple ".d" folders in `top`
                        layer = Layer(dir_mo.group("layer"),
                                      root,
                                      physical=os.path.join(top, dir_),
                                      logical=os.path.join(top_dirname, mount_mo.group("realname")),
                                      config=self.config,
                                      file_cls=File)
                        self.add_layer(layer)
                        self._mount_points[top].append(dir_)
                    else:
                        # XXX: Give the user the option of logging the near-matches (could indicate a
                        # problem in the config, or could be some other legit directory structure)
                        '''
                        print("LAYER NEAR MISS:  {} looks like a mount point, but {} doesn't "
                              "follow the expected convention".format(top, dir_))
                        '''
                        pass
            elif top.endswith(".d"):
                '''
                print("MOUNT NEAR MISS:  {}".format(top))
                '''
                pass

        # XXX: Adding <root> should be skipped if (and only if) root itself if a '.d' folder
        # Very last operation, add the top directory as the final layer (lowest rank)
        prune_points = [os.path.join(mount, layer) for mount, layers in self._mount_points.items()
                        for layer in layers]
        layer = Layer("<root>", root, None, None, config=self.config, file_cls=File,
                      prune_points=prune_points)
        self.add_layer(layer, do_sort=False)
        self._root_layer = layer

    def list_layers(self):
        # Return all but the root layer.
        # Avoiding self._layers[:-1] because there could be cases where root isn't included.
        return [l for l in self._layers if l is not self._root_layer]

    def order_layers(self):
        # Sort based on layer name (or other sorting priority:  00-<name> to 99-<name>
        self._layers.sort(key=lambda l: l.name)
