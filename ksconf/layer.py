from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch
from os import PathLike, stat_result
from pathlib import Path, PurePath
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterator, Optional, Pattern, Sequence, Type, Union
from warnings import warn

from ksconf.compat import Dict, List, Set, Tuple
from ksconf.hook import plugin_manager
from ksconf.util.file import file_hash, relwalk, secure_delete
from ksconf.version import version_info

try:
    # Fallback for Python 3.7
    from functools import cached_property
except ImportError:
    cached_property = property

"""
Each Layer Collection has one or more 'Layer', each layer has one or more 'File's.

LayerCollection methods:

    - list_files():   Return superset of all file names returned by all layers (order undefined)
    - walk():         Return list_files() like content in a os.walk() (or relwalker) like way --
                      must consider directory order, useful for copying tree, for example.
                      Assumption for now:  Don't return layer per file, just what files exist.
                      Ask about layers per file later.
    - list_layers():  Iterate over layer objects (metadata retrievable, on demand)
    - get_file():     Return files (in ranked layer order)
    - calculate_signature():
                      Get a dictionary describing the on-disk state of an app

Other possible methods:
    list_dirs():      Return list of known directories?   Not sure how we want this part to work.
                      Perhaps walk() is good enough?


dotD style layers:

    LayerCollectionDotD:  has one or more 'LayerMount', each LayerMount has one or more Layer,
                          which has one or more 'File's.



Remember:  This must work for NON-layered directories too, hopefully with minimal overhead.

This must work with an explicitly given list of layers

"""

no_path = PurePath()


# Exceptions

class LayerException(Exception):
    pass


class LayerUsageException(LayerException):
    pass


@dataclass
class LayerContext:
    # Other attributes may dynamically be added by plugins or custom classed derived from LayerFile
    follow_symlink: bool = False
    block_files: Pattern = re.compile(r"\.(bak|swp)$")
    block_dirs: set = field(default_factory=lambda: {".git"})
    template_variables: dict = field(default_factory=dict)


@dataclass
class _FileFactoryHandler:
    name: str
    handler: Type[LayerFile]
    priority: int = 0
    enabled: bool = False


class FileFactory:
    _registered_handlers: Dict[str, _FileFactoryHandler] = {}
    _enabled_handlers: List[Callable] = []

    def __init__(self):
        # Make this class a singleton?
        self._context_state: tuple = ()

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

    def __call__(self, layer, path: PurePath, *args, **kwargs) -> Union[LayerFile, None]:
        """
        Factory thats finds the appropriate LayerFile class and returns a new instance.
        """
        for cls in self._enabled_handlers:
            if cls.match(path):
                return cls(layer, path, *args, **kwargs)

    def register_handler(self, name: str, **kwargs):
        def wrapper(handler_class: Type[LayerFile]) -> Type[LayerFile]:
            handler = _FileFactoryHandler(name, handler_class, **kwargs)
            self._registered_handlers[handler.name] = handler
            self._recalculate()
            return handler_class
        return wrapper

    def __enter__(self) -> FileFactory:
        """
        Context manager that allows settings to be temporarily applied and then
        cleanly reverted at exit.  Used for internal unit testing.
        """
        assert not self._context_state, "Nested contexts are not supported"
        from copy import deepcopy
        self._context_state = (deepcopy(self._registered_handlers),
                               deepcopy(self._enabled_handlers))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._registered_handlers, self._enabled_handlers = self._context_state
        self._context_state = ()


# Single shared instance
layer_file_factory = FileFactory()
register_file_handler = layer_file_factory.register_handler


@register_file_handler("default", priority=-100, enabled=True)
class LayerFile(PathLike):
    '''
    Abstraction of a file within a Layer

    Path definitions

    ..

    ``logical_path``
        Conceptual file path.  This is the final path after all layers are resolved.
        Think of this as the 'destination' file.
        The file name, directory, or extension may be different from what's on the filesystem.

    ``physical_path``
        Actual file system path.  The location of the physical file found within a source layer.
        This file contains either the actual content of a file or the input material by which the
        file's contents are generated.

    ``resource_path``
        Content location.  Often this the ``physical_path``, but in the case of abstracted layers
        (like templates, or archived layers), this would be the location of a temporary resource that contains
        the expanded/rendered content.

    Example:

    Given the file ``default.d/30-my-org/indexes.conf.j2``, the paths are:

        * ``logical_path``: default/indexes.conf
        * ``physical_path``: default.d/30-my-org/indexes.conf.j2
        * ``resource_path``: /tmp/<RANDOM>-indexes.conf (temporary with automatic cleanup; see subclasses)

    '''
    # Are slots helpful here?  (parent class already has __dict__), need that for cached_properties
    __slots__ = ["layer", "relative_path", "_stat"]

    def __init__(self,
                 layer: Layer,
                 relative_path: PurePath,
                 stat: Optional[stat_result] = None):
        self.layer = layer
        self.relative_path = relative_path
        self._stat = stat

    def __fspath__(self) -> str:
        return str(self.resource_path)

    @staticmethod
    def match(path: PurePath):
        """
        Determine if this class can handle the given (:py:obj:`path`) based on name matching.
        """
        return True

    @cached_property
    def physical_path(self) -> Path:
        return Path(self.layer.root, self.layer.physical_path, self.relative_path)

    @cached_property
    def logical_path(self) -> Path:
        return Path(self.layer.logical_path, self.relative_path)

    @property
    def resource_path(self):
        # For "normal" files, the resource_path is the physical_path (not true for rendered files)
        return self.physical_path

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

    def calculate_signature(self) -> Dict[str, Union[str, int]]:
        """
        Calculate a unique content signature used for change detection.

        Simple or cheap methods are preferred over expensive ones.  That being said, in some
        situations like template rendering that relies on external variables, where there is no way
        to accurately detect changes without fully rendering.  In such cases, a full cryptographic
        hash of the rendered output is necessary.

        Output should be JSON safe.
        """
        stat = self.stat
        return {
            "mtime": int(stat.st_mtime),
            "ctime": int(stat.st_ctime),
            "size": stat.st_size,
        }


class LayerRenderedFile(LayerFile):
    """
    Abstract LayerFile for rendered scenarios, such as template scenarios.
    A subclass really only needs to implement ``match()`` ``render()``
    """
    __slots__ = ["_rendered_resource"]

    use_secure_delete = False

    # True: hash rendered content; False: use stats-based check (same as base class)
    signature_requires_resource_hash = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rendered_resource: Path = None  # type: ignore

    def __del__(self):
        if getattr(self, "_rendered_resource", None) and self._rendered_resource.is_file():
            if self.use_secure_delete:
                # Use (slightly-more) secure deletion.
                # Note that in a packaging operation, for example, there are many temporary files
                # that could contain sensitive data.  This is very imperfect.
                secure_delete(self._rendered_resource)
            else:
                self._rendered_resource.unlink()

    def render(self, template_path: Path) -> str:
        raise NotImplementedError

    @staticmethod
    def transform_name(path: PurePath) -> PurePath:
        # Remove trailing suffix
        return path.with_name(path.stem)

    @cached_property
    def logical_path(self) -> Path:
        return Path(self.layer.logical_path,
                    self.transform_name(self.relative_path))

    @cached_property
    def physical_path(self) -> Path:
        return Path(self.layer.root, self.layer.physical_path, self.relative_path)

    @property
    def resource_path(self) -> Path:
        if not self._rendered_resource:
            # Temporary file will be removed in instance destructor.  Multiple opens expected.
            tf = NamedTemporaryFile(delete=False)
            self._rendered_resource = Path(tf.name)
            content = self.render(self.physical_path)
            self._rendered_resource.write_text(content)
        return self._rendered_resource

    def calculate_signature(self) -> Dict[str, Union[str, int]]:
        """
        Calculate a unique content signature used for change detection based on the rendered template output.

        Note that subclasses can control this by setting :py:attr:`signature_requires_resource_hash` to False,
        this indicate that rendered output is deterministic based on changes to the physical_path.
        """
        if self.signature_requires_resource_hash:
            return {
                "hash": file_hash(self.resource_path)
            }
        else:
            return super().calculate_signature()


@register_file_handler("jinja", priority=50, enabled=False)
class LayerFile_Jinja2(LayerRenderedFile):

    signature_requires_resource_hash = True     # Changes in 'template_vars' can vary rendered output
    use_secure_delete = False

    @staticmethod
    def match(path: PurePath):
        return path.suffix == ".j2"

    @staticmethod
    def transform_name(path: PurePath) -> PurePath:
        return path.with_name(path.name[:-3])

    @property
    def jinja2_env(self):
        # Use context object to 'cache' the jinja2 environment
        if not hasattr(self.layer.context, "jinja2_environment"):
            self.layer.context.jinja2_environment = self._build_jinja2_env()  # type: ignore
        return self.layer.context.jinja2_environment  # type: ignore

    def _build_jinja2_env(self):
        from jinja2 import Environment, FileSystemLoader, StrictUndefined
        environment = Environment(
            undefined=StrictUndefined,
            loader=FileSystemLoader(self.layer.root),
            auto_reload=False)

        # Call plugin for jinja environment tweaking
        plugin_manager.hook.modify_jinja_env(env=environment)

        environment.globals.update(self.layer.context.template_variables)
        return environment

    def render(self, template_path: Path) -> str:
        rel_template_path = template_path.relative_to(self.layer.root)
        template = self.jinja2_env.get_template("/".join(rel_template_path.parts))
        value = template.render()
        return value


class LayerFilter:
    """
    Container for filter rules that can be applied via :py:meth:`~LayerCollectionBase.apply_filter`.
    The action of the last matching rule wins.  Wildcard matching is supported using fnmatch().
    When no rules are given, the filter accepts all layers.

    The action of the first rule determines the matching mode or non-matching behavior.  That is,
    if the first rule is 'exclude', then the first rule become 'include *'.
    """
    _valid_actions = ("include", "exclude")

    def __init__(self):
        self._rules = []

    def add_rule(self, action: str, pattern: str):
        """ Add include/exclude rule for layer name matching. """
        # If no filter rules have been setup yet, be sure to set the default
        if action not in self._valid_actions:
            raise ValueError(f"Unknown action of {action}.  "
                             f"Valid actions are: {self._valid_actions}")
        if not self._rules:
            if action == "include":
                first_filter = ("exclude", "*")
            else:
                first_filter = ("include", "*")
            self._rules.append(first_filter)
        self._rules.append((action, pattern))
        return self

    def add_rules(self, rules):
        for action, pattern in rules:
            self.add_rule(action, pattern)
        return self

    def evaluate(self, layer: Layer) -> bool:
        """ Evaluate if layer matches the given rule set. """
        response = True
        layer_name = layer.name
        for rule_action, rule_pattern in self._rules:
            if fnmatch(layer_name, rule_pattern):
                response = rule_action == "include"
        return response

    __call__ = evaluate


R_walk = Iterator[Tuple[Path, List[str], List[str]]]


class LayerType(Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"


class Layer:
    """ Basic layer container:   Connects logical and physical paths.

    An explicit layer is that has been clearly marked or labeled.  Depending on
    the exact layering scheme in use, this may take different forms.  Layers
    that are have no marking or indicator are implicit layers.  This could be
    a plain directory contain a simple Splunk app, or the top-level folder of
    a complex app that contains multiple explicit layers.

    Files on the filesystem are scanned one time and then cached.
    """
    __slots__ = ["name", "root", "logical_path", "physical_path", "context",
                 "type", "_file_factory", "_cache_files"]

    def __init__(self, name: str,
                 root: Path,
                 physical: PurePath,
                 logical: PurePath,
                 context: LayerContext,
                 *,
                 file_factory: Callable = layer_file_factory,
                 type: LayerType = LayerType.EXPLICIT):
        self.name = name
        self.root = root
        self.type = type
        self.physical_path = physical
        self.logical_path = logical
        self.context = context
        self._file_factory = file_factory
        self._cache_files: Dict[PurePath, LayerFile] = None  # type: ignore

    def __len__(self) -> int:
        if self._cache_files is None:
            self._build_cache()
        return len(self._cache_files)

    def __repr__(self):
        return f"<{self.__class__.__name__} [{self.name}] {len(self)} files root={self.root}>"

    def walk(self) -> R_walk:
        """
        Low-level walk over the file system, blocking unwanted file patterns
        and given directories.  Paths are relative.
        """
        # In the simple case, this is good enough.   Some subclasses will need to override
        for (root, dirs, files) in relwalk(Path(self.root, self.physical_path),
                                           followlinks=self.context.follow_symlink):
            root = Path(root)
            files = [f for f in files if not self.context.block_files.search(f)]
            for d in list(dirs):
                if d in self.context.block_dirs:
                    dirs.remove(d)
            yield (root, dirs, files)

    def iter_files(self) -> Iterator[LayerFile]:
        """ Low-level loop over files without caching. """
        for (top, _, files) in self.walk():
            for file in files:
                yield self._file_factory(self, top / file)

    def _build_cache(self):
        self._cache_files = {lf.logical_path: lf for lf in self.iter_files()}

    def list_files(self) -> List[LayerFile]:
        """ Get a list of LayerFile objects.  Cache enabled. """
        if self._cache_files is None:
            self._build_cache()
        return list(self._cache_files.values())

    def get_file(self, path: PurePath) -> Union[LayerFile, None]:
        """ Return file object (by logical path), if it exists in this layer. """
        if self._cache_files is None:
            self._build_cache()
        lf = self._cache_files.get(path)
        if lf and lf.physical_path.is_file():
            return lf

    def block_file(self, path: PurePath) -> bool:
        """ Block a file (remove from cache).  This prevents processing.
        No action is taken on :py:attr:`physical_file`. """
        # NOTE:  Resetting the cache would loose any removal info.  Not supported.
        if self._cache_files is None:
            self._build_cache()
        try:
            del self._cache_files[path]
            return True
        except KeyError:
            return False


class LayerCollectionBase:
    """ A collection of layer containers which contains layer files.

    Note:  All 'path's here are relative to the ROOT.
    """

    def __init__(self, context: Optional[LayerContext] = None):
        self._layers: List[Layer] = []
        self._layers_blocked: List[Layer] = []
        self._files_blocked: List[LayerFile] = []
        self.context = context or LayerContext()

    def __len__(self):
        """ Determine total number of active layers (implicit + explicit).  Blocked layers are not counted. """
        return len(self._layers)

    def apply_layer_filter(self, layer_filter: LayerFilter) -> bool:
        """
        Apply a destructive filter to all explicit layers.  ``layer_filter(layer)`` is called
        once per layer, and True means the layer is retain. Implicit layers cannot be blocked.
        Returns True if any layers were blocked.
        """
        changed = False
        for layer in list(self._layers):
            if layer.type == LayerType.IMPLICIT:
                # Must keep
                continue
            elif not layer_filter(layer):
                self.block_layer(layer)
                changed = True
        return changed

    def apply_path_filter(self, path_filter: Callable[[PurePath], bool]) -> bool:
        """
        Apply a path filter to all logical paths.  After file filtering, any
        layers no longer containing files are also blocked.
        """
        logical_to_layer: Dict[PurePath, List[Layer]] = defaultdict(list)
        for layer in self._layers:
            for lf in layer.list_files():
                logical_to_layer[lf.logical_path].append(layer)

        discard = []
        for logical_path, layers in logical_to_layer.items():
            if not path_filter(logical_path):
                discard.append(logical_path)
                for layer in layers:
                    layer.block_file(logical_path)
        self._files_blocked.extend(discard)

        if discard:
            # Remove explicit layers that are now empty
            for layer in list(self._layers):
                if layer.type != LayerType.IMPLICIT and len(layer) == 0:
                    self.block_layer(layer)
            return True
        return False

    def apply_filter(self, layer_filter: LayerFilter) -> bool:
        """ Legacy name.  Use :py:method:`apply_layer_filter` instead. """
        if version_info > (0, 15):
            warn("Please use apply_layer_filter() instead of apply_filter()", DeprecationWarning)
        return self.apply_layer_filter(layer_filter)

    @staticmethod
    def order_layers(layers: List[Layer]) -> List[Layer]:
        """ Simple ordering so that explicit layers come before implicit layers.
        Otherwise layer order is preserved. """
        return sorted(layers, key=lambda layer: layer.type.value)

    def add_layer(self, layer: Layer, do_sort=True):
        self._layers.append(layer)
        if do_sort:
            self._layers = self.order_layers(self._layers)

    def block_layer(self, layer: Layer):
        """
        Remove a layer from the active set of layers.

        Blocked layers are internally remembered for the :py:meth:`list_all_layer_names` use case.
        """
        if layer in self._layers:
            assert layer.type != LayerType.IMPLICIT, "Unable to block an implicit layer"
            self._layers.remove(layer)
            self._layers_blocked.append(layer)

    def list_layers(self) -> List[Layer]:
        return self._layers

    def iter_layers_by_name(self, name: str) -> Iterator[Layer]:
        for layer in self.list_layers():
            if layer.name == name:
                yield layer

    def list_layer_names(self) -> List[str]:
        """ Return a list the names of all remaining layers. """
        return [l.name for l in self.list_layers()]

    def list_all_layer_names(self) -> List[str]:
        """ Return the full list of all discovered layers.  This will not change
        before/after :py:meth:`apply_layer_filter` or :py:meth:apply_path_filter` is called. """
        if self._layers_blocked:
            layers = self.order_layers(self.list_layers() + self._layers_blocked)
            return [l.name for l in layers]
        else:
            return self.list_layer_names()

    def iter_all_files(self) -> Iterator[LayerFile]:
        """ Iterator over all physical files. """
        # This method bypasses layer caching
        for layer in self._layers:
            yield from layer.iter_files()

    def list_physical_files(self) -> List[Path]:
        files = set()
        for file_ in self.iter_all_files():
            files.add(file_.physical_path)
        return list(files)

    def list_logical_files(self) -> List[Path]:
        """ Return a list of logical paths. """
        files = set(f.logical_path for l in self._layers for f in l.list_files())
        return list(files)

    def get_files(self, path: PurePath) -> List[LayerFile]:
        """ return all layers associated with the given relative path. """
        files = []
        for layer in self._layers:
            file_ = layer.get_file(path)
            if file_:
                files.append(file_)
        return files

    def get_file(self, path: PurePath) -> Iterator[LayerFile]:
        """ Confusingly named.  For backwards compatibility.
        Use :py:meth:`get_files` instead. """
        if version_info > (0, 15):
            warn("Please use get_files() not get_file()", DeprecationWarning)
        return iter(self.get_files(path))

    def calculate_signature(self,
                            relative_paths: bool = True,
                            key_factory: Optional[Callable[[Path], Any]] = None
                            ) -> dict:
        """
        Calculate the full signature of all LayerFiles into a nested dictionary structure
        """
        data = {}
        for lf in self.iter_all_files():
            key = lf.physical_path
            if relative_paths:
                key = key.relative_to(lf.layer.root)
            if callable(key_factory):
                key = key_factory(key)
            data[key] = lf.calculate_signature()
        return data

    # Legacy names
    list_files = list_logical_files
    get_layers_by_name = iter_layers_by_name    # No known usages


class MultiDirLayerCollection(LayerCollectionBase):
    """
    A very simple LayerCollection implementation that allow one or more directories to act as
    layers.  These layers must be given as explicitly, without any automatic detection mechanisms.

    Consider this the legacy layer implementation.
    """

    def add_layer(self, path: Path):
        # Layer name should be considered arbitrary and unimportant here
        layer_name = path.name
        if not path.is_dir():
            raise LayerUsageException("Layers must be directories.  "
                                      f"Given path '{path}' is not a directory.")
        layer = Layer(layer_name, path, no_path, no_path, context=self.context,
                      file_factory=layer_file_factory)
        super().add_layer(layer)


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
A:  Multiple LayerCollections SHOULD be supported.

    MyApp/                          <- LayerCollection & Layer (Anonymous -- lowest ranking)
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


class DotdLayer(Layer):
    __slots__ = ["prune_points"]

    def __init__(self, name: str,
                 root: Path,
                 physical: PurePath,
                 logical: PurePath,
                 context: LayerContext,
                 *,
                 file_factory: Callable = layer_file_factory,
                 type: LayerType = LayerType.EXPLICIT,
                 prune_points: Optional[Sequence[Path]] = None):
        super().__init__(
            name, root, physical, logical, context=context, type=type,
            file_factory=file_factory)
        self.prune_points: Set[Path] = set(prune_points) if prune_points else set()

    def walk(self) -> R_walk:
        for (root, dirs, files) in super().walk():
            if root in self.prune_points:
                # Cleanup files/dirs to keep walk() from descending deeper
                del dirs[:]
            else:
                yield (root, dirs, files)


# Q:  How do we mark "mount-points" in the directory structure to keep multiple layers
#     from claiming the same files?????
class DotDLayerCollection(LayerCollectionBase):

    '''
    class MountBase:
        def __init__(self, path):
            self.path = path

    class MountTransparent(MountBase):
        """ Pass through files as-is, no manipulation. """
        pass

    class MountDotD(MountBase):
        def __init__(self, path):
            super().__init__(path)
    '''

    mount_regex = re.compile(r"(?P<realname>[\w_.-]+)\.d$")
    layer_regex = re.compile(r"(?P<layer>\d\d-[\w_.-]+)")

    def __init__(self, context=None):
        super().__init__(context)
        self._mount_points: Dict[Path, List[str]] = defaultdict(list)

    def set_root(self, root: Path, follow_symlinks=None):
        # XXX:  Rename this to "discover()"  "add_path",  "from_dir", ...?
        #       (Ideally this should be the same for all LayerCollection classes)
        #       Drop the 'follow_symlink' param and rely on context instead.
        """ Set a root path, and auto discover all '.d' directories.

        Note:  We currently only support ``.d/<layer>`` directories, a file like
        ``props.conf.d/10-upstream`` won't be handled here.
        A valid name would be ``default.d/10-name/props.conf``.
        """
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
                        layer = DotdLayer(dir_mo.group("layer"),
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
        layer = DotdLayer("<root>", root, no_path, no_path, context=self.context,
                          type=LayerType.IMPLICIT,
                          file_factory=layer_file_factory,
                          prune_points=prune_points)
        self.add_layer(layer, do_sort=False)

    def list_layers(self) -> List[DotdLayer]:
        # Return all but the root layer.
        # Avoiding self._layers[:-1] because there could be cases where root isn't included.
        return [l for l in self._layers if l.type != LayerType.IMPLICIT]

    @classmethod
    def order_layers(cls, layers: List[Layer]) -> List[Layer]:
        """
        Sort layers based on layer name (or other sorting priority:  00-<name> to 99-<name>
        """
        layers = sorted(layers, key=lambda l: l.name)
        return super().order_layers(layers)


def build_layer_collection(source: Path,
                           layer_method: str,
                           context: Optional[LayerContext] = None,
                           ) -> LayerCollectionBase:
    if context is None:
        context = LayerContext()
    if layer_method == "dir.d":
        collection = DotDLayerCollection(context)
        collection.set_root(source, context.follow_symlink)
    elif layer_method == "disable":
        collection = MultiDirLayerCollection(context)
        collection.add_layer(source)
    else:
        raise NotImplementedError(f"layer_method of '{layer_method}' is not supported.  "
                                  "Please use 'dir.d' or 'disable'.")
    return collection


# LEGACY class names (for backwards compatibility)
LayerRootBase = LayerCollectionBase
DotDLayerRoot = DotDLayerCollection
DirectLayerRoot = MultiDirLayerCollection
