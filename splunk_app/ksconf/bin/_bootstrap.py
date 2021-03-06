"""
KSCONF Boostrap shim to get the python path setup correctly.
"""
import os
import sys

this_module = os.path.abspath(__file__)
ksconf_app = os.path.dirname(this_module)
ksconf_modules = os.path.join(ksconf_app, "lib")
sys.path.insert(0, ksconf_modules)

# Remove current dir from path, so import 'ksconf' doesn't incorrectly import ksconf.py
for p in ("", ksconf_app):
    if p in sys.path:
        sys.path.remove(p)
