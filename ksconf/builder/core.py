# -*- coding: utf-8 -*-
"""


Cache build requirements:

    * Caching mechanism should inspet 'inputs' (collect file hashes) to determine if any content has
      changed.  If input varies, then command should be re-run.
    * Command (decorated function) should be generally unaware of all other details of build process,
      and it should *ONLY* be able to see files listed in "inputs"
    * Allow caching to be fully disabled (run in-place with no dir proxying) for CI/CD
    * Cache should have allow a timeout parameter


decorator used to implement caching:
    * decorator args:
        * inputs:       list or glob
        * outputs       (do we need this, can we just detect this??)
                        Default to "." (everything)
        * timeout=0     Seconds before cache should be considered stale
        * name=None     If not given, default to the short name of the function.
                        (Cache "slot"), must be filesystem safe]
"""

from functools import wraps
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Union

from ksconf.builder import QUIET, VERBOSE, BuildCacheException, BuildStep
from ksconf.builder.cache import CachedRun, FileSet


def _get_function_sourcecode_hash(f):
    import hashlib
    import inspect
    h = hashlib.new("sha256")
    code = inspect.getsource(f).encode("utf-8")
    h.update(code)
    return h.hexdigest()


class BuildManager:
    """ Management of individual build steps

    .. versionadded:: v0.8.0
    """

    def __init__(self):
        self.source_path = None
        self.build_path = None
        self.dist_path = None
        self.cache_path = None
        self._cache_enabled = True
        self._taint = False
        self._folder_set = False

    def taint_cache(self):
        self._taint = True

    def disable_cache(self):
        self._cache_enabled = False

    def get_build_step(self, output=None):
        kw = {}
        if output:
            kw["output"] = output
        step = BuildStep(self.build_path, self.source_path, self.dist_path, **kw)
        return step

    def set_folders(self, source_path, build_path, dist_path=None):
        self._folder_set = True
        self.source_path = Path(source_path).absolute()
        self.build_path = Path(build_path).absolute()
        if dist_path:
            self.dist_path = Path(dist_path).absolute()
        else:
            # Assume 'dist' lives along side 'build'
            self.dist_path = self.build_path.with_name("dist")
        self.cache_path = self.build_path.with_suffix(".cache")

    def is_folders_set(self):
        return self._folder_set

    def get_cache_info(self, name):
        path = self.cache_path / name
        cache_info = CachedRun(path)
        if self._taint:
            cache_info.taint()
        if not self._cache_enabled:
            cache_info.disable()
        return cache_info

    def cache(self, inputs: List[str], outputs: int,
              timeout: int = None,
              name: str = None,
              cache_invalidation: Union[dict, list, str] = None) -> None:
        """ function decorator for caching build steps
        Wrapped function must accept BuildStep instance as first parameters

        XXX:  Clearly document what things are good cache candidates and which are not.

        Example:

            * No extra argument to the function (at least currently)
            * Changes to inputs files are not supported
            * Deleting files aren't supported
            * Can only operate in a single directory given a limited set of inputs
            * Cannot read from the source directory, and agrees not to write to dist
              (In other words, limit all activities to build_path for deterministic behavior)
        """
        name_ = name
        cache_settings = {
            "name": name,
            "inputs": inputs,
            "outputs": outputs,
            "timeout": timeout,
            "cache_invalidation": cache_invalidation,
        }

        def decorator(f):
            # nonlocal name
            if name_ is None:
                name = f.__name__.split(".")[-1]

            f_source_hash = _get_function_sourcecode_hash(f)
            cache_settings["function_code_hash"] = f_source_hash

            @wraps(f)
            def wrapper(build_step: BuildStep) -> None:
                log = build_step.get_logger(name)
                use_cache = True
                cache = self.get_cache_info(name)

                # After the first cached build step is executed, block access to source path
                build_step.source_path = None

                if cache.is_disabled:
                    log("Caching disabled", VERBOSE)
                    # Run directly with no additional
                    return f(build_step)

                if cache.exists:
                    try:
                        cache.load()
                    except Exception as e:
                        log(f"Failed to load cache:  {e}", QUIET)
                        use_cache = False
                if cache._settings:
                    # Always use the most up-to-date value for timeout
                    cache.set_settings({"timeout": timeout})
                    try:
                        for setting in cache_settings:
                            if cache_settings[setting] != cache._settings[setting]:
                                log(f"Cache invalided due to setting '{setting}': "
                                    f"{cache_settings[setting]} was "
                                    f"{cache._settings[setting]}")
                                use_cache = False
                                break
                    except KeyError as e:
                        log(f"Cache invalided due to missing setting {e}")
                        use_cache = False
                # TODO: Check for cache tampering (confirm that existing files haven't
                #       been modified); user requestable
                current_inputs = FileSet.from_filesystem(self.source_path, inputs)
                # Determine if previous cache entry exists, and if the input files are the same
                if not cache.exists:
                    log("No cache found", VERBOSE)
                    use_cache = False
                elif not cache.inputs_identical(current_inputs):
                    # XXX: Tell user which file(s) changed?
                    log("Cache skipped due to change in inputs.  Will re-run.")
                    use_cache = False
                elif cache.is_expired:
                    log("Cache expired.  Will re-run.")
                    use_cache = False
                if use_cache:
                    # Cache HIT:  Reuse cache, by simply copying the outputs to the build folder
                    log("Cache used")
                    cached_output = cache.cached_outputs
                    cached_output.copy_all(cache.cache_dir, self.build_path)
                    log(f"Reused {len(cached_output)} output objects from cache", VERBOSE)
                    # XXX:  VERBOSE 3 should list all expanded files
                else:
                    # Cache MISS: Prepare to call the wrapped function
                    # 1. √ Make temporary location
                    # 2. √ Copy inputs to temp locations
                    # 3. √ Run wrapped functionality
                    # 4. √ Expand output into FileSet (Collect)
                    # 5. √ Store metadata (inputs/outputs/...) to JSON
                    # 6. √ Copy output to real build folder

                    # Make temporary folder for executing wrapped function
                    with TemporaryDirectory(dir=self.cache_path,
                                            prefix=f"{name}-tmp-") as temp_dir:
                        # NOTE: Make a 't' dir under the temp folder so that the cache.rename() doesn't remove the
                        #       folder managed by TemporaryDirectory, which it doesn't like.
                        temp_dir = Path(temp_dir) / "t"
                        final_cache_root = cache.root
                        cache = CachedRun(temp_dir)
                        alt_bs = build_step.alternate_path(cache.cache_dir)
                        # XXX: Copy any other settings from the original 'build_step' to our copied version
                        # Collect inputs from the source directory and copy them to the temporary directory
                        fs_inputs = FileSet.from_filesystem(self.source_path, inputs)
                        fs_inputs.copy_all(self.source_path, cache.cache_dir)
                        log(f"Copied {len(fs_inputs)} input files", VERBOSE * 2)
                        log(f"Copied input files: {', '.join(str(p) for p in fs_inputs)}", VERBOSE * 3)
                        try:
                            # Run wrapped function
                            ret = f(alt_bs)
                            if ret is not None:
                                raise NotImplementedError("A return value not supported for cached build steps")
                        except Exception as e:
                            log(f"Failed during executing.  Error: {e}", QUIET * 2)
                            # XXX: More error handling here.  Add custom exception class
                            raise
                        # TODO: Check for change to inputs.  This could lead to nondeterministic results
                        fs_inputs2 = FileSet.from_filesystem(cache.cache_dir, inputs)
                        if fs_inputs != fs_inputs2:
                            log("Inputs changed during execution", QUIET * 2)
                            raise BuildCacheException("Inputs were modified")
                        fs_outputs = FileSet.from_filesystem(cache.cache_dir, outputs)
                        # Store input/output fingerprint to the internal cache state and persist to disk
                        log(f"Capture {len(fs_outputs)} outputs")
                        cache.set_settings(cache_settings)
                        cache.set_cache_info("inputs", fs_inputs)
                        cache.set_cache_info("outputs", fs_outputs)
                        cache.dump()
                        # Copy output files to real build directory
                        fs_outputs.copy_all(cache.cache_dir, self.build_path)
                        cache.rename(final_cache_root)
                # No return (on purpose); as we don't want to track extra state

            wrapper.inputs = inputs
            wrapper.outputs = outputs
            wrapper.timeout = timeout
            wrapper.name = name
            return wrapper
        return decorator
