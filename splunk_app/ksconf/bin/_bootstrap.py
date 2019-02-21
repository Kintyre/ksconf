"""
KSCONF Boostrap shim to get the python path setup correctly.
"""
import sys
import os

this_module = os.path.abspath(__file__)
ksconf_app = os.path.dirname(this_module)
ksconf_modules = os.path.join(ksconf_app, "lib")
sys.path.insert(0,ksconf_modules)

# Remove current working dir from the import path, so we can import 'ksconf' without importing ksconf.py in this directory
for p in ("", ksconf_app):
    if p in sys.path:
        sys.path.remove(p)
