from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatch
from os import PathLike, stat_result
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import Callable, Iterator, Match

from ksconf.compat import Dict, List, Set, Tuple
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
    Drop any None
    """
    return Path(*filter(None, parts))


# Exceptions

class LayerException(Exception):
    pass


class LayerUsageException(LayerException):
    pass


@dataclass
class LayerContext:
    follow_symlink: bool = False
    block_files: Match = re.compile(r"\.(bak|swp)$")
    block_dirs: set = field(default_factory=lambda: {".git"})
    template_variables: dict = field(default_factory=dict)


@dataclass
class _FileFactoryHandler:
    name: str
    handler: LayerFile
    priority: int = 0
    enabled: bool = False


class FileFactory:
    _registered_handlers: Dict[str, _FileFactoryHandler] = {}
    _enabled_handlers: List[Callable] = []

    def __init__(self):
        # Make this class a singleton?
        self._context_state = None

    def _recalculate(self):
        self._enabled_handlers = [
            h.handler for h in sorted(self._registered_handlers.values(),
                                      key=lambda h: (-h.priority, h.name)) if h.enabled]

    def enable(self, name, _enabled=True):
        handler = self._registered_handlers[name]
        handler.enabled = _enabled
        self._recalculate()

    def disable(self, name):
        self.enable(name, False)

    def list_available_handlers(self) -> List[str]:
        return [h.name for h in self._registered_handlers.values() if not h.enabled]

    def __call__(self, layer, path: PurePath, *args, **kwargs) -> LayerFile:
        """
        Factory thats finds the appropriate LayerFile class and returns a new instance.
        """
        for cls in self._enabled_handlers:
            if cls.match(path):
                return cls(layer, path, *args, **kwargs)

    def register_handler(self, name: str, **kwargs):
        def wrapper(handler_class: LayerFile):
            handler = _FileFactoryHandler(name, handler_class, **kwargs)
            self._registered_handlers[handler.name] = handler
            self._recalculate()
            return handler_class
        return wrapper

    def __enter__(self) -> FileFactory:
        # The primary use case is for clean unit testing
        assert not self._context_state, "Nested contexts are not supported"
        from copy import deepcopy
        self._context_state = (deepcopy(self._registered_handlers),
                               deepcopy(self._enabled_handlers))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._registered_handlers, self._enabled_handlers = self._context_state
        self._context_state = None


# Single shared instance
layer_file_factory = FileFactory()
register_file_handler = layer_file_factory.register_handler


@register_file_handler("default", priority=-100, enabled=True)
class LayerFile(PathLike):
    '''
    Abstraction of a file within a Layer

    Paths:
        * ``logical_path``:  Conceptual file path.  This is the final path after all layers are resolved.
          Think of this as the 'destination' file.
        * ``physical_path``:  Actual file path.  The location of the physical file found within a source layer.
          Most of the time this is the 'source' file, however this doesn't take into considerations layer combining or
          template expansion requirements.  (In the case of a template, this would be the template file)
        * ``resource_path``:  Content location.  Often this the ``physical_path``, but in the case of abstracted layers
          (like templates, or archived layers), this would be the location of a temporary resource that contains
          the expanded/rendered content.
    '''
    __slots__ = ["layer", "relative_path", "_stat"]

    def __init__(self,
                 layer: LayerRootBase.Layer,
                 relative_path: PurePath,
                 stat: stat_result = None):
        self.layer = layer
        self.relative_path = relative_path
        self._stat = stat

    def __fspath__(self) -> str:
        return self.resource_path

    @staticmethod
    def match(path: PurePath):
        return True

    @property
    def physical_path(self) -> Path:
        return _path_join(self.layer.root, self.layer.physical_path, self.relative_path)

    @property
    def logical_path(self) -> Path:
        return _path_join(self.layer.logical_path, self.relative_path)

    # For "normal" files, the resource_path is the physical_path (not true for rendered files)
    resource_path = physical_path

    @property
    def stat(self) -> stat_result:
        if self._stat is None:
            self._stat = self.physical_path.stat()
        return self._stat

    @property
    def size(self):
        return self.stat.st_size

    @property
    def mtime(self):
        return self.stat.st_mtime


class LayerRenderedFile(LayerFile):
    """
    Abstract LayerFile for rendered scenarios, such as template scenarios.
    A subclass really only needs to implement ``match()`` ``render()``
    """
    __slots__ = ["_rendered_resource"]

    def __init__(self, *args, **kwargs):
        super(LayerRenderedFile, self).__init__(*args, **kwargs)
        self._rendered_resource = None

    def __del__(self):
        if getattr(self, "_rendered_resource", None) and self._rendered_resource.is_file():
            self._rendered_resource.unlink()

    def render(self, template_path: Path) -> str:
        raise NotImplementedError

    @staticmethod
    def transform_name(path: PurePath):
        # Remove trailing suffix
        return path.with_name(path.stem)

    @property
    def logical_path(self) -> Path:
        return _path_join(self.layer.logical_path,
                          self.transform_name(self.relative_path))

    @property
    def physical_path(self) -> Path:
        return _path_join(self.layer.root, self.layer.physical_path, self.relative_path)

    @property
    def resource_path(self) -> Path:
        if not self._rendered_resource:
            # Temporary file will be removed in instance destructor.  Multiple opens expected.
            tf = NamedTemporaryFile(delete=False)
            self._rendered_resource = Path(tf.name)
            content = self.render(self.physical_path)
            self._rendered_resource.write_text(content)
        return self._rendered_resource


@register_file_handler("jinja", priority=50, enabled=False)
class LayerFile_Jinja2(LayerRenderedFile):
    @staticmethod
    def match(path: PurePath):
        return path.suffix == ".j2"

    @staticmethod
    def transform_name(path: PurePath):
        return path.with_name(path.name[:-3])

    @property
    def jinja2_env(self):
        # Use context object to 'cache' the jinja2 environment
        if not hasattr(self.layer.context, "jinja2_environment"):
            self.layer.context.jinja2_environment = self._build_jinja2_env()
        return self.layer.context.jinja2_environment

    def _build_jinja2_env(self):
        from jinja2 import Environment, FileSystemLoader, StrictUndefined
        environment = Environment(
            undefined=StrictUndefined,
            loader=FileSystemLoader(self.layer.root),
            auto_reload=False)
        environment.globals.update(self.layer.context.template_variables)
        return environment

    def render(self, template_path: Path) -> str:
        self.jinja2_env
        rel_template_path = template_path.relative_to(self.layer.root)
        template = self.jinja2_env.get_template("/".join(rel_template_path.parts))
        value = template.render()
        return value


class LayerFilter:
    _valid_actions = ("include", "exclude")

    def __init__(self):
        self._rules = []

    def add_rule(self, action, pattern):
        # If no filter rules have been setup yet, be sure to set the default
        if action not in self._valid_actions:
            raise ValueError(f"Unknown action of {action}.  "
                             f"Valid actions include: {self._valid_actions}")
        if not self._rules:
            if action == "include":
                first_filter = ("exclude", "*")
            elif "exclude":
                first_filter = ("include", "*")
            self._rules.append(first_filter)
        self._rules.append((action, pattern))

    def evaluate(self, layer: LayerRootBase.Layer) -> bool:
        response = True
        layer_name = layer.name
        for rule_action, rule_pattern in self._rules:
            if fnmatch(layer_name, rule_pattern):
                response = rule_action == "include"
        return response

    __call__ = evaluate


R_walk = Iterator[Tuple[Path, List[str], List[str]]]


class LayerRootBase:
    """ All 'path's here are relative to the ROOT. """

    class Layer:
        """ Basic layer Container:   Connects logical and physical paths. """
        __slots__ = ["name", "root", "logical_path", "physical_path", "context",
                     "_file_factory", "_cache_files"]

        def __init__(self, name: str,
                     root: Path,
                     physical: PurePath,
                     logical: PurePath,
                     context: LayerContext,
                     file_factory: Callable):
            self.name = name
            self.root = root
            self.physical_path = physical
            self.logical_path = logical
            self.context = context
            self._file_factory = file_factory
            self._cache_files: List[LayerFile] = []

        def walk(self) -> R_walk:
            # In the simple case, this is good enough.   Some subclasses will need to override
            for (root, dirs, files) in relwalk(_path_join(self.root, self.physical_path),
                                               followlinks=self.context.follow_symlink):
                root = Path(root)
                files = [f for f in files if not self.context.block_files.search(f)]
                for d in list(dirs):
                    if d in self.context.block_dirs:
                        dirs.remove(d)
                yield (root, dirs, files)

        def iter_files(self) -> Iterator[LayerFile]:
            for (top, _, files) in self.walk():
                for file in files:
                    yield self._file_factory(self, top / file)

        def list_files(self) -> List[LayerFile]:
            if not self._cache_files:
                self._cache_files = list(self.iter_files())
            return self._cache_files

        def get_file(self, path: Path) -> LayerFile:
            """ Return file object (by logical path), if it exists in this layer. """
            # TODO:  Optimize by caching.  Use a dict with a logical_path as the key
            for file in self.list_files():
                if file.logical_path == path:
                    if file.physical_path.is_file():
                        return file
                    else:
                        return None

    # LayerRootBase
    def __init__(self, context: LayerContext = None):
        self._layers: List[LayerRootBase.Layer] = []
        self.context = context or LayerContext()

    def apply_filter(self, layer_filter: LayerFilter) -> bool:
        """
        Apply a destructive filter to all layers.  layer_filter(layer) will be called one for each
        layer, if the filter returns True than the layer is kept.  Root layers are always kept.

        Returns True if layers were removed
        """
        layers = [l for l in self._layers if layer_filter(l)]
        result = self._layers != layers
        self._layers = layers
        return result

    def order_layers(self):
        raise NotImplementedError

    def add_layer(self, layer: Layer, do_sort=True):
        self._layers.append(layer)
        if do_sort:
            self.order_layers()

    def list_layers(self) -> List[Layer]:
        return self._layers

    def get_layers_by_name(self, name: str) -> Iterator[LayerRootBase.Layer]:
        for layer in self.list_layers():
            if layer.name == name:
                yield layer

    def list_layer_names(self) -> List[str]:
        return [l.name for l in self.list_layers()]

    def iter_all_files(self) -> Iterator[LayerFile]:
        """ Iterator over all physical files. """
        for layer in self._layers:
            yield from layer.iter_files()

    def list_physical_files(self) -> List[LayerFile]:
        files = set()
        for file_ in self.iter_all_files():
            files.add(file_.physical_path)
        return list(files)

    def list_logical_files(self) -> List[LayerFile]:
        """ Return a list of logical paths. """
        files = set()
        for file_ in self.iter_all_files():
            files.add(file_.logical_path)
        return list(files)

    def get_file(self, path) -> Iterator[LayerFile]:
        """ return all layers associated with the given relative path. """
        for layer in self._layers:
            file_ = layer.get_file(path)
            if file_:
                yield file_

    # Legacy names
    list_files = list_logical_files


class DirectLayerRoot(LayerRootBase):
    """
    A very simple direct LayerRoot implementation that relies on all layer paths to be explicitly
    given without any automatic detection mechanisms.  You can think of this as the legacy
    implementation.
    """

    def add_layer(self, path: Path):
        Layer = self.Layer
        # Layer name should be considered arbitrary and unimportant here
        layer_name = path.name
        if not path.is_dir():
            raise LayerUsageException("Layers must be directories.  "
                                      f"Given path '{path}' is not a directory.")
        layer = Layer(layer_name, path, None, None, context=self.context,
                      file_factory=layer_file_factory)
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

        def __init__(self, name: str,
                     root: Path,
                     physical: PurePath,
                     logical: PurePath,
                     context: LayerContext,
                     file_factory: Callable,
                     prune_points: Set[Path] = None):
            super(DotDLayerRoot.Layer, self).__init__(name, root, physical, logical, context=context,
                                                      file_factory=file_factory)
            self.prune_points: Set[Path] = set(prune_points) if prune_points else set()

        def walk(self) -> R_walk:
            for (root, dirs, files) in super(DotDLayerRoot.Layer, self).walk():
                if root in self.prune_points:
                    # Cleanup files/dirs to keep walk() from descending deeper
                    del dirs[:]
                else:
                    yield (root, dirs, files)

    '''
    class MountBase:
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

    def __init__(self, context=None):
        super(DotDLayerRoot, self).__init__(context)
        # self.root = None
        self._root_layer: LayerRootBase.Layer = None
        self._mount_points: Dict[Path, List[str]] = defaultdict(list)

    def apply_filter(self, layer_filter: LayerFilter):
        # Apply filter function, but also be sure to keep the root layer
        def fltr(l):
            return l is self._root_layer or layer_filter(l)
        return super(DotDLayerRoot, self).apply_filter(fltr)

    def set_root(self, root: Path, follow_symlinks=None):
        """ Set a root path, and auto discover all '.d' directories.

        Note:  We currently only support '.d/<layer>' directories, a file like
        `default.d/10-props.conf` won't be handled here.
        A valid name would be ``default.d/10-name/props.conf``.
        """
        Layer = self.Layer
        root = Path(root)
        if follow_symlinks is None:
            follow_symlinks = self.context.follow_symlink

        for (top, dirs, files) in relwalk(root, topdown=False, followlinks=follow_symlinks):
            del files
            top = Path(top)
            mount_mo = self.mount_regex.match(top.name)
            if mount_mo:
                for dir_ in dirs:
                    dir_mo = self.layer_regex.match(dir_)
                    if dir_mo:
                        # XXX: Nested layers breakage, must substitute multiple ".d" folders in `top`
                        layer = Layer(dir_mo.group("layer"),
                                      root,
                                      physical=top / dir_,
                                      logical=top.parent / mount_mo.group("realname"),
                                      context=self.context,
                                      file_factory=layer_file_factory)
                        self.add_layer(layer)
                        self._mount_points[top].append(dir_)
                    else:
                        # XXX: Give the user the option of logging the near-matches (could indicate a
                        # problem in the config, or could be some other legit directory structure)
                        '''
                        print(f"LAYER NEAR MISS:  {top} looks like a mount point, but {dir_} doesn't "
                              "follow the expected convention")
                        '''
                        pass
            elif top.name.endswith(".d"):
                '''
                print(f"MOUNT NEAR MISS:  {top}")
                '''
                pass

        # XXX: Adding <root> should be skipped if (and only if) root itself if a '.d' folder
        # Very last operation, add the top directory as the final layer (lowest rank)
        prune_points = [mount / layer
                        for mount, layers in self._mount_points.items()
                        for layer in layers]
        layer = Layer("<root>", root, None, None, context=self.context,
                      file_factory=layer_file_factory,
                      prune_points=prune_points)
        self.add_layer(layer, do_sort=False)
        self._root_layer = layer

    def list_layers(self) -> List[Layer]:
        # Return all but the root layer.
        # Avoiding self._layers[:-1] because there could be cases where root isn't included.
        return [l for l in self._layers if l is not self._root_layer]

    def order_layers(self):
        # Sort based on layer name (or other sorting priority:  00-<name> to 99-<name>
        self._layers.sort(key=lambda l: l.name)
