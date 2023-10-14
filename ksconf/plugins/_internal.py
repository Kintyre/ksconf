""" Placeholder for any internal plugins

NOTE:  This is NOT yet enabled via entrypoints
"""

from ksconf.hook import ksconf_hook

'''
@ksconf_hook
def modify_jinja_env(env):
    pass
'''

# Keep flake8 happy
del ksconf_hook
