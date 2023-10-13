API Reference
=============

..  note::  As of now, no assumptions should be made about APIs remaining stable

    KSCONF is first and foremost a CLI tool, so backwards incompatible changes are more of a concern for CLI breakage than for API breakage.
    That being said, there are a number of helpful features in the core ``ksconf`` Python module.
    So if anyone is interested in using the API, please feel free to do so, but let us know *how* you are using it
    and we'll find a way to keep the the important bits stable.
    We'd love to make it more clear what APIs are stable and which are likely to change.

    As of right now, the general rule of thumb is this:
    Anything well-covered by the unit tests should be be fairly safe to build on top of, but again, :ref:`ping us <contact_us>`.
    Also, things used in the `cdillc.splunk`_ Ansible Collection should be fairly safe too.
    There's a decent bit of back and forth between these two projects driving feature development.


..  commments

    API Highlights
    --------------

    These things should be stable:

    * ksconf.parser.parse_conf
    * ksconf.parser.write_conf
    * ksconf.parser.update_conf

    (This is an incomplete list...  I need to figure out a better way to handle this, preferably with Sphinx.  If you know how, drop me a line!)
    There's only so many hours in a day!


KSCONF API
----------

..  toctree::
    :maxdepth: 4

    api/modules
    build_example



..  _api_ksconf_version:

Version information
-------------------

For code bases using ksconf, sometimes behaviors have to vary based on ksconf version.

In general, the best approach is to either (1) specify a hard version requirement in a packaging, or (2) if you have to support a wider range of versions use the `EAFP <https://docs.python.org/3.9/glossary.html#term-eafp>`_ approach of asking for forgiveness rather than permission.
In other words, simply try to import the module or call then method you need and if the modules doesn't exist or the new method argument doesn't exist yet, capture that in an exception.

Other times a direct version number is helpful to evaluate or simply report to the user.
Here's the approach works across the widest range of ksconf versions:

..  code-block:: python

    try:
        from ksconf.version import version, version_info
    except ImportError:
        from ksconf._version import version
        # If you need version_info; if not drop this next line
        version_info = tuple(int(p) if p.isdecimal() else p for p in version.split("."))



..  note::  Historic version capture

    In ksconf 0.12.0, the suggested method was to simply use:


    ..  code-block:: python

        from ksconf import __version__

    This is simple and straight forward.
    However this no longer works as of version 0.13 and later due to migration to a namespace package and this is no longer viable.
    Therefore, we recommend approach detailed above.




..  include:: common
