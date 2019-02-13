Known issues
------------


General
========

-   File encoding issues:
-   Byte order markers and specific encodings are NOT preserved. All file
    will be written out as UTF-8, by default.


Splunk app
==========

-   File cleanup issues after *KSCONF app for Splunk* upgrades.  This can be caused by old `.dist-info`
    folders or other stale files left around from between versions.  If you encounter this issue,
    either uninstall (and, if necessary wipe the directory) or just manually remove the old dist-info
    folders.  A proper solution for this is needed. (GH issue #37)


See more `confirmed bugs <https://github.com/Kintyre/ksconf/labels/bug>`__
in the issue tracker.
