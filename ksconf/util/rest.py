from __future__ import absolute_import, unicode_literals

from typing import Optional


def build_rest_namespace(base: str,
                         owner: Optional[str] = None,
                         app: Optional[str] = None) -> str:
    if owner and app:
        p = (base, "servicesNS", owner, app)
    elif app:
        p = (base, "servicesNS", "nobody", app)
    elif owner:
        raise ValueError("Can't specify user without app!")
    else:
        p = (base, "services")
    return "/".join(p)


def build_rest_url(base: str,
                   service: str,
                   owner: Optional[str] = None,
                   app: Optional[str] = None) -> str:
    prefix = build_rest_namespace(base, owner, app)
    return f"{prefix}/{service}"
