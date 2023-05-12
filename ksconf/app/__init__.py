# -*- coding: utf-8 -*-
""" Splunk App helper classes

Note that these representations are for native Splunk apps that use 'default'
and 'local' and have not built-in concept of ksconf layers.
"""

from __future__ import absolute_import, annotations, unicode_literals

from pathlib import Path

from ksconf.app.facts import AppFacts
from ksconf.app.manifest import AppManifest
from ksconf.compat import Tuple


def get_facts_manifest_from_archive(
        archive: Path,
        calculate_hash=True,
        check_paths=True) -> Tuple[AppFacts, AppManifest]:
    """ Get both AppFacts and AppManifest from a single archive.
    If ``calculate_hash`` is True, then the manifest will contain checksums for
    all files in the archive.  Without this, it's not possible to calculate a
    hash for the combined manifest.

    Use this function to collect both metadata about the app and a full listing
    of the app's contents.
    """
    # XXX: Optimize to create AppFacts and AppManifest concurrently; from a single read of the archive.
    # XXX: Use this in ksconf.commands.unarchive
    archive = Path(archive)

    facts = AppFacts.from_archive(archive)
    manifest = AppManifest.from_archive(archive, calculate_hash=calculate_hash)
    if check_paths:
        manifest.check_paths()

    return facts, manifest
