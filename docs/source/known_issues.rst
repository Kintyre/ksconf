Known issues
------------


General
========

-   File encoding issues: Byte order markers and specific encodings are NOT preserved.
    All files are encoding using UTF-8 upon update, which is Splunk's expected encoding.


Splunk app
==========

-   File cleanup issues after *KSCONF app for Splunk* upgrades (impacts versions prior to 0.7.0).
    Old :file:`.dist-info` folders or other stale files may be left around after upgrades.
    If you encounter this issue, either uninstall and delete the ksconf directory or manually remove the old 'bin' folder and (re)upgrade to the latest version.
    The fix in 0.7.0 is to remove the version-specific portion of the folder name.  (GH issue #37)


See more `confirmed bugs <https://github.com/Kintyre/ksconf/labels/bug>`__
in the issue tracker.
