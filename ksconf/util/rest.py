from __future__ import absolute_import, unicode_literals


def build_rest_namespace(base, owner=None, app=None):
    if owner and app:
        p = (base, "servicesNS", owner, app)
    elif app:
        p = (base, "servicesNS", "nobody", app)
    elif owner:
        raise ValueError("Can't specify user without app!")
    else:
        p = (base, "services")
    return "/".join(p)


def build_rest_url(base, service, owner=None, app=None):
    prefix = build_rest_namespace(base, owner, app)
    return prefix + "/" + service
