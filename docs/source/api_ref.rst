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
